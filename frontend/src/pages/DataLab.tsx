import DataLabPanel from '@/components/ml/DataLabPanel'

export default function DataLab() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 pb-20 md:pb-8">
      <div className="container-custom py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Data Lab</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            JupyterLab workspace for training/evaluation and offline analysis (metrics, models, pcaps).
          </p>
        </div>

        <DataLabPanel />
      </div>
    </div>
  )
}
