import AiConsole from '@components/ai/AiConsole'

export default function AiConsoleAdmin() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 pb-20 md:pb-8">
      <div className="container-custom py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">AI Console (Admin)</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Global console for all projects/topologies.
          </p>
        </div>
        <AiConsole />
      </div>
    </div>
  )
}

