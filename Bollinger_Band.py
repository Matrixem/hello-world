# coding=utf-8
from pyalgotrade import strategy
from pyalgotrade import plotter
from pyalgotrade.technical import bollinger
from pyalgotrade.barfeed.csvfeed import GenericBarFeed
from pyalgotrade.bar import Frequency
from pyalgotrade import broker
from pyalgotrade.broker import slippage, backtesting, fillstrategy
from pyalgotrade.stratanalyzer import returns, sharpe, drawdown, trades


class BBands(strategy.BacktestingStrategy):
    def __init__(self, feed, instrument1, instrument2, instrument3, bBandsPeriod, brk):
        #传入变量
        # feed---每一个交易日的数据
        # instrument1-----价差
        # instrument2-----沪金
        # instrument3-----COMEX黄金
        # bBandsPeriod----布林带的均线周期长度
        # brk-------------订单的情况
        super(BBands, self).__init__(feed, brk)
        self.__instrument1 = instrument1
        self.__instrument2 = instrument2
        self.__instrument3 = instrument3
        self.__bbands = bollinger.BollingerBands(feed[instrument1].getCloseDataSeries(), bBandsPeriod, 1.5)   #获取布林带的指令
        self.getBroker()   #调用订单的设置

    def getBollingerBands(self):
        return self.__bbands

    def __getOrderSize(self, bars):      #持仓量设置
        cash = self.getBroker().getCash(False)
        price_AU = bars[self.__instrument2].getClose()
        price_GC = bars[self.__instrument3].getClose()
        # 沪金和COMEX黄金的总克数
        AU_size = int(cash/(price_GC*6.5/31.1035+price_AU))  #cash * 31*1000*6.1/(31*1000*6.1+10*3110.35))
        GC_size = int(AU_size/3.1035)   #cash * 10*3110.35/(31*1000*6.1+10*3110.35))
        return (AU_size, GC_size)

    def buySpread(self, bars):
        amount1, amount2 = self.__getOrderSize(bars)      #做多沪金，做空COMEX黄金
        self.marketOrder(self.__instrument2, amount1)
        self.marketOrder(self.__instrument3, amount2 * -1)

    def sellSpread(self, bars):
        amount1, amount2 = self.__getOrderSize(bars)   #做空沪金，做多COMEX黄金
        self.marketOrder(self.__instrument2, amount1 * -1)
        self.marketOrder(self.__instrument3, amount2)

    def reducePosition(self, instrument):                      #平仓操作
        currentPos = self.getBroker().getShares(instrument)
        if currentPos > 0:
            self.marketOrder(instrument, currentPos * -1)
        elif currentPos < 0:
            self.marketOrder(instrument, currentPos * -1)

    def onBars(self, bars):                               #策略
        lower = self.__bbands.getLowerBand()[-1]
        upper = self.__bbands.getUpperBand()[-1]
        middle = self.__bbands.getMiddleBand()[-1]
        if lower is None:   #出现下轨线才进行下一步操作
            return

        shares2 = self.getBroker().getShares(self.__instrument2)
        shares3 = self.getBroker().getShares(self.__instrument3)
        diff = bars[self.__instrument1]           #价差

        shares = abs(shares2) + abs(shares3)        #总持仓的黄金克数
        if diff.getClose()<lower and shares == 0:
            self.buySpread(bars)
        elif diff.getClose() > upper and shares2 > 0 and shares3 < 0:
            self.reducePosition(self.__instrument2)
            self.reducePosition(self.__instrument3)
            self.sellSpread(bars)

        elif diff.getClose()>upper and shares == 0:
            #print 'Short AU & Long GC'
            self.sellSpread(bars)
        elif diff.getClose() < lower and shares2 < 0 and shares3 > 0:
            self.reducePosition(self.__instrument2)
            self.reducePosition(self.__instrument3)
            self.buySpread(bars)


        '''    
        elif diff.getClose()>middle and shares2>0 and shares3<0:
            print'reducePosition'
            self.reducePosition(self.__instrument2)
            self.reducePosition(self.__instrument3)
        elif diff.getClose()<middle and shares2<0 and shares3>0:
            print'reducePosition'
            self.reducePosition(self.__instrument2)
            self.reducePosition(self.__instrument3)  '''


        '''
            if shares2 < 0 and shares3 > 0:
                self.reducePosition(self.__instrument2)
                self.reducePosition(self.__instrument3)
                self.buySpread(bars)
        elif diff.getClose() > upper and shares == 0:
            self.sellSpread(bars)
            if shares2 > 0 and shares3 < 0:
                self.reducePosition(self.__instrument2)
                self.reducePosition(self.__instrument3)
                self.sellSpread(bars)
        elif shares != 0 and abs(diff.getClose() - middle) < 0.25 :
            self.reducePosition(self.__instrument2)
            self.reducePosition(self.__instrument3) '''



def main(plot):
    instrument = ["price_diff", 'SHFE_AU', 'COMEX_AU']
    bBandsPeriod = 20

    # Download the bars.
    feed = GenericBarFeed(Frequency.DAY, None, None)
    feed.addBarsFromCSV('price_diff', 'price_oneyear_diff.csv')
    feed.addBarsFromCSV('SHFE_AU', 'AU_oneyear_samedate.csv')
    feed.addBarsFromCSV('COMEX_AU', 'GC_oneyear_samedate.csv')

    # 3. broker setting
    broker_commission = broker.backtesting.FixedPerTrade(390)  # 2230

    fill_stra = broker.fillstrategy.DefaultStrategy(volumeLimit=1)
    sli_stra = broker.slippage.VolumeShareSlippage(priceImpact=0.2)
    fill_stra.setSlippageModel(sli_stra)

    brk = broker.backtesting.Broker(10000000, feed, broker_commission)
    brk.setFillStrategy(fill_stra)

    strat = BBands(feed, instrument[0], instrument [1], instrument[2], bBandsPeriod, brk)
    sharpeRatioAnalyzer = sharpe.SharpeRatio()
    strat.attachAnalyzer(sharpeRatioAnalyzer)
    trade_situation = trades.Trades()
    strat.attachAnalyzer(trade_situation)
    draw_down = drawdown.DrawDown()
    strat.attachAnalyzer(draw_down)
    returning = returns.Returns()
    strat.attachAnalyzer(returning)

    if plot:
        plt = plotter.StrategyPlotter(strat, True, True, True)
        plt.getInstrumentSubplot(instrument[0]).addDataSeries("upper", strat.getBollingerBands().getUpperBand())
        plt.getInstrumentSubplot(instrument[0]).addDataSeries("middle", strat.getBollingerBands().getMiddleBand())
        plt.getInstrumentSubplot(instrument[0]).addDataSeries("lower", strat.getBollingerBands().getLowerBand())

    strat.run()
    strat.info('最终资产值: ¥ %.2f' % strat.getResult())                #info表示记录每一次的交易
    print '夏普率: ', sharpeRatioAnalyzer.getSharpeRatio(0.05, False)   #print表示只打印一次
    print '累计收益率：', (returning.getCumulativeReturns()[-1])
    print '最大回撤：', draw_down.getMaxDrawDown()
    print '总交易次数：', trade_situation.getCount()
    print '每次交易的手续费：', trade_situation.getCommissionsForAllTrades()
    print '赚钱的交易次数：', trade_situation.getProfitableCount()
    print '亏损的交易次数：', trade_situation.getUnprofitableCount()
    print '不赚不亏的交易次数：', trade_situation.getEvenCount()
    print '每次交易的盈亏：', trade_situation.getAll()

    if plot:
        plt.plot()


if __name__ == "__main__":
    main(True)