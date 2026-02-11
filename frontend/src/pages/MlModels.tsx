import MlModelsPanel from '@/components/ml/MlModelsPanel'

export default function MlModels() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 pb-20 md:pb-8">
      <div className="container-custom py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">ML Models</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Upload and select operational ML models/algorithms for streaming decisions (anomaly, routing, MANO).
          </p>
        </div>

        <MlModelsPanel />
      </div>
    </div>
  )
}

