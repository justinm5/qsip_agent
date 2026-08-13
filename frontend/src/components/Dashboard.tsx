import { useState } from 'react'
import BacktestPanel from './BacktestPanel'
import MarketChart from './MarketChart'
import PaperPortfolio from './PaperPortfolio'
import PortfolioPanel from './PortfolioPanel'
import ResearchResults from './ResearchResults'
import SignalExplain from './SignalExplain'
import SignalStream from './SignalStream'
import SignalTable from './SignalTable'
import TopRecommendations from './TopRecommendations'

export default function Dashboard() {
  const [selectedTicker, setSelectedTicker] = useState('AAPL')
  const [selectedSignal, setSelectedSignal] = useState<string | null>(null)

  return (
    <div className="p-4 lg:p-6 max-w-[1600px] mx-auto">
      <header className="mb-6 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-emerald-400 tracking-tight">
            QSIP Agent
          </h1>
          <p className="text-slate-400 text-sm">
            Quant Signal Intelligence Platform — research, signals, paper trading & live recommendations
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-slate-400">Ticker</label>
          <input
            type="text"
            value={selectedTicker}
            onChange={(e) => setSelectedTicker(e.target.value.toUpperCase())}
            className="bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-emerald-500 uppercase"
          />
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <TopRecommendations />
        <PaperPortfolio />
        <ResearchResults />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <SignalStream />
        <MarketChart ticker={selectedTicker} />
        <BacktestPanel ticker={selectedTicker} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <PortfolioPanel />
        <SignalExplain signalId={selectedSignal || ''} />
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-slate-300 mb-2">Selected Signal</h2>
          <p className="text-slate-500 text-sm">{selectedSignal || 'Click a signal in the table to view SHAP explanation.'}</p>
        </div>
      </div>

      <SignalTable onSelectTicker={setSelectedTicker} onSelectSignal={setSelectedSignal} />
    </div>
  )
}
