#include "sierrachart.h"

SCDLLName("MA Trading Strategy")

void LogTradeInfo(SCStudyInterfaceRef& sc, int index, const char* action, float price, float profit) 
{
    SCDateTime barTime = sc.BaseDateTimeIn[index];
    char LogText[300];
    
    if (profit != 0) {
        sprintf_s(LogText, 
            "%s\n"
            "时间: %04d-%02d-%02d %02d:%02d:%02d\n"
            "价格: %.2f\n"
            "盈亏: %.2f", 
            action,
            barTime.GetYear(), barTime.GetMonth(), barTime.GetDay(), 
            barTime.GetHour(), barTime.GetMinute(), barTime.GetSecond(),
            price, profit);
    } else {
        sprintf_s(LogText, 
            "%s\n"
            "时间: %04d-%02d-%02d %02d:%02d:%02d\n"
            "价格: %.2f", 
            action,
            barTime.GetYear(), barTime.GetMonth(), barTime.GetDay(), 
            barTime.GetHour(), barTime.GetMinute(), barTime.GetSecond(),
            price);
    }
    sc.AddMessageToLog(LogText, 0);
}

SCSFExport scsf_MAStrategy(SCStudyInterfaceRef sc)
{
    // 定义持久化变量
    SCSubgraphRef PositionState = sc.Subgraph[0];    // 持仓状态
    SCSubgraphRef MAEntry = sc.Subgraph[1];          // 入场移动平均线
    SCSubgraphRef MAExit = sc.Subgraph[2];           // 出场移动平均线
    SCFloatArrayRef EntryPrice = sc.Subgraph[3];     // 开仓价格
    SCSubgraphRef TradeProfit = sc.Subgraph[4];      // 交易盈亏
    SCSubgraphRef TotalTrades = sc.Subgraph[5];      // 总交易数
    SCSubgraphRef WinningTrades = sc.Subgraph[6];    // 盈利交易数
    SCSubgraphRef TotalProfit = sc.Subgraph[7];      // 总盈利
    SCSubgraphRef TotalLoss = sc.Subgraph[8];        // 总亏损

    if (sc.SetDefaults)
    {
        sc.GraphName = "Dual MA Trading Strategy";
        sc.StudyDescription = "双均线交易策略";
        
        sc.AutoLoop = 1;
        
        // 设置画图风格
        MAEntry.Name = "Entry MA";
        MAEntry.DrawStyle = DRAWSTYLE_LINE;
        MAEntry.PrimaryColor = RGB(255, 255, 0);
        
        MAExit.Name = "Exit MA";
        MAExit.DrawStyle = DRAWSTYLE_LINE;
        MAExit.PrimaryColor = RGB(0, 255, 255);
        
        PositionState.Name = "Position State";
        PositionState.DrawStyle = DRAWSTYLE_POINT;
        PositionState.PrimaryColor = RGB(255, 255, 255);
        
        // 添加入场均线周期输入
        sc.Input[0].Name = "Entry MA Period";
        sc.Input[0].SetInt(20);
        sc.Input[0].SetDescription("入场移动平均线周期");
        
        // 添加出场均线周期输入
        sc.Input[1].Name = "Exit MA Period";
        sc.Input[1].SetInt(10);
        sc.Input[1].SetDescription("出场移动平均线周期");
        
        return;
    }
    
    // 初始化
    if (sc.Index == 0)
    {
        PositionState[0] = 0;
        EntryPrice[0] = 0;
        TradeProfit[0] = 0;
        TotalTrades[0] = 0;
        WinningTrades[0] = 0;
        TotalProfit[0] = 0;
        TotalLoss[0] = 0;
        return;
    }
    
    // 复制前一个状态
    int i = sc.Index;
    if (i > 0) {
        PositionState[i] = PositionState[i-1];
        EntryPrice[i] = EntryPrice[i-1];
        TradeProfit[i] = TradeProfit[i-1];
        TotalTrades[i] = TotalTrades[i-1];
        WinningTrades[i] = WinningTrades[i-1];
        TotalProfit[i] = TotalProfit[i-1];
        TotalLoss[i] = TotalLoss[i-1];
    }

    // 计算两条移动平均线
    sc.MovingAverage(sc.BaseDataIn[SC_LAST], MAEntry, MOVAVGTYPE_SIMPLE, sc.Input[0].GetInt());
    sc.MovingAverage(sc.BaseDataIn[SC_LAST], MAExit, MOVAVGTYPE_SIMPLE, sc.Input[1].GetInt());
    
    float current_price = sc.Close[i];
    float ma_entry_value = MAEntry[i];
    float ma_exit_value = MAExit[i];
    
    // 交易逻辑
    if (current_price > ma_entry_value) { // 价格上穿入场均线，做多
        if (PositionState[i] < 0) { // 当前持有空仓，平仓
            float profit = EntryPrice[i] - current_price;
            TradeProfit[i] += profit;
            
            // 更新统计
            TotalTrades[i]++;
            if (profit > 0) {
                WinningTrades[i]++;
                TotalProfit[i] += profit;
            } else {
                TotalLoss[i] -= profit;
            }
            
            LogTradeInfo(sc, i, "平空仓", current_price, profit);
        }
        
        if (PositionState[i] <= 0) { // 开多仓
            PositionState[i] = 1;
            EntryPrice[i] = current_price;
            LogTradeInfo(sc, i, "开多仓", current_price, 0);
        }
    }
    else if (current_price < ma_exit_value) { // 价格下穿出场均线，做空
        if (PositionState[i] > 0) { // 当前持有多仓，平仓
            float profit = current_price - EntryPrice[i];
            TradeProfit[i] += profit;
            
            // 更新统计
            TotalTrades[i]++;
            if (profit > 0) {
                WinningTrades[i]++;
                TotalProfit[i] += profit;
            } else {
                TotalLoss[i] -= profit;
            }
            
            LogTradeInfo(sc, i, "平多仓", current_price, profit);
        }
        
        if (PositionState[i] >= 0) { // 开空仓
            PositionState[i] = -1;
            EntryPrice[i] = current_price;
            LogTradeInfo(sc, i, "开空仓", current_price, 0);
        }
    }

    // 在最后一个Bar输出统计结果
    if (i == sc.ArraySize - 1) {
        SCDateTime startTime = sc.BaseDateTimeIn[0];
        SCDateTime endTime = sc.BaseDateTimeIn[i];
        char StatsText[600];
        float winRate = TotalTrades[i] > 0 ? (float)WinningTrades[i] / TotalTrades[i] * 100 : 0;
        float profitFactor = TotalLoss[i] > 0 ? TotalProfit[i] / TotalLoss[i] : 0;
        
        sprintf_s(StatsText, 
            "\n=== Strategy Statistics ===\n,"
            "Backtesting time range:\n,"
            "  Start: %04d-%02d-%02d %02d:%02d\n,"
            "  End: %04d-%02d-%02d %02d:%02d\n,"
            "Total bars: %d\n,"
            "Total trades: %.0f\n,"
            "Winning trades: %.0f\n,"
            "Win rate: %.2f%%\n,"
            "Total profit: %.2f\n,"
            "Total loss: %.2f\n,"
            "Profit factor: %.2f\n,"
            "Net profit: %.2f\n,"
            "===============",
            startTime.GetYear(), startTime.GetMonth(), startTime.GetDay(), 
            startTime.GetHour(), startTime.GetMinute(),
            endTime.GetYear(), endTime.GetMonth(), endTime.GetDay(), 
            endTime.GetHour(), endTime.GetMinute(),
            sc.ArraySize,
            TotalTrades[i],
            WinningTrades[i],
            winRate,
            TotalProfit[i],
            TotalLoss[i],
            profitFactor,
            TradeProfit[i]
        );
        
        sc.AddMessageToLog(StatsText, 0);
    }
}
