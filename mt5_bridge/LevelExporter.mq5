//+------------------------------------------------------------------+
//|                                       LevelExporter.mq5           |
//|                                                                    |
//| Runs inside MT5 as an Expert Advisor. Every few seconds, scans   |
//| every object drawn on the chart (horizontal lines, trendlines,   |
//| Fibonacci retracements) and writes their current price levels    |
//| out to a JSON file that the Python alert engine reads.           |
//|                                                                    |
//| SETUP:                                                            |
//|   1. Open MetaEditor (F4 inside MT5, or Tools -> MetaQuotes       |
//|      Language Editor)                                             |
//|   2. File -> New -> Expert Advisor (template) -> paste this in   |
//|      (or File -> Open, if you saved this .mq5 into your          |
//|      MQL5/Experts folder directly)                                |
//|   3. Click Compile (F7). Fix any red errors before continuing —  |
//|      compilers on different MT5 builds occasionally need minor   |
//|      syntax tweaks; this targets standard MQL5.                  |
//|   4. Back in MT5: drag "LevelExporter" from the Navigator panel  |
//|      (under Expert Advisors) onto your XAU/USD chart.             |
//|   5. A dialog appears — go to the "Common" tab and make sure      |
//|      "Allow File I/O" is checked (or Allow Algo Trading globally  |
//|      allowed). Click OK.                                          |
//|   6. Draw a horizontal line, trendline, or Fibonacci on your      |
//|      chart as normal (Insert -> Line Studies / Fibonacci).        |
//|                                                                    |
//| OUTPUT FILE LOCATION (fixed, same on every machine):              |
//|   %APPDATA%\MetaQuotes\Terminal\Common\Files\levels_export.json   |
//|   (i.e. C:\Users\<you>\AppData\Roaming\MetaQuotes\Terminal\       |
//|    Common\Files\levels_export.json)                               |
//+------------------------------------------------------------------+
#property copyright "Free Market Monitor"
#property version   "1.00"
#property strict

input int RefreshSeconds = 5;   // how often to re-scan and re-export

//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(RefreshSeconds);
   ExportLevels(); // export once immediately on attach, don't wait for first timer tick
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
}

//+------------------------------------------------------------------+
void OnTimer()
{
   ExportLevels();
}

//+------------------------------------------------------------------+
// Escapes characters that would break JSON string literals.
string JsonEscape(string s)
{
   StringReplace(s, "\\", "\\\\");
   StringReplace(s, "\"", "\\\"");
   return s;
}

//+------------------------------------------------------------------+
void ExportLevels()
{
   string json = "{\n";
   json += "  \"exported_at\": \"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + "\",\n";
   json += "  \"symbol\": \"" + _Symbol + "\",\n";
   json += "  \"levels\": [\n";

   int total = ObjectsTotal(0, -1, -1);
   bool first = true;
   datetime now = TimeCurrent();

   for(int i = 0; i < total; i++)
   {
      string name = ObjectName(0, i, -1, -1);
      long   type = ObjectGetInteger(0, name, OBJPROP_TYPE);

      string levelType = "";
      double price = 0.0;
      bool   valid = false;

      if(type == OBJ_HLINE)
      {
         levelType = "hline";
         price = ObjectGetDouble(0, name, OBJPROP_PRICE, 0);
         valid = true;
      }
      else if(type == OBJ_TREND)
      {
         levelType = "trendline";
         // Current extrapolated price of the trendline AT THIS MOMENT —
         // this is what lets a diagonal line act as a live crossable level.
         price = ObjectGetValueByTime(0, name, now, 0);
         valid = true;
      }
      else if(type == OBJ_FIBO)
      {
         // A single Fibonacci object has MULTIPLE levels (23.6%, 38.2%, etc).
         // Export each configured level as its own entry.
         double price1 = ObjectGetDouble(0, name, OBJPROP_PRICE, 0);
         double price2 = ObjectGetDouble(0, name, OBJPROP_PRICE, 1);
         int levelCount = (int)ObjectGetInteger(0, name, OBJPROP_LEVELS);

         for(int lvl = 0; lvl < levelCount; lvl++)
         {
            double ratio = ObjectGetDouble(0, name, OBJPROP_LEVELVALUE, lvl);
            // Standard retracement: 0% sits at the first anchor, 100% at
            // the second anchor, other ratios interpolated between them.
            double levelPrice = price1 + ratio * (price2 - price1);

            if(!first) json += ",\n";
            json += "    {\"name\": \"" + JsonEscape(name) + "_fib" + DoubleToString(ratio*100, 1) + "\", ";
            json += "\"type\": \"fibo\", ";
            json += "\"ratio\": " + DoubleToString(ratio, 4) + ", ";
            json += "\"price\": " + DoubleToString(levelPrice, _Digits) + "}";
            first = false;
         }
         continue; // already wrote entries for this object, skip the single-price path below
      }
      else
      {
         continue; // not a level type we care about (arrows, text, etc.)
      }

      if(valid)
      {
         if(!first) json += ",\n";
         json += "    {\"name\": \"" + JsonEscape(name) + "\", ";
         json += "\"type\": \"" + levelType + "\", ";
         json += "\"price\": " + DoubleToString(price, _Digits) + "}";
         first = false;
      }
   }

   json += "\n  ]\n}\n";

   // FILE_COMMON writes to a fixed, predictable path shared across all MT5
   // installs on this machine, regardless of which broker/terminal —
   // makes it easy for the Python side to always know where to look.
   int handle = FileOpen("levels_export.json", FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(handle != INVALID_HANDLE)
   {
      FileWriteString(handle, json);
      FileClose(handle);
   }
   else
   {
      Print("LevelExporter: failed to open output file, error ", GetLastError());
   }
}
