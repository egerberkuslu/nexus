import { useState, useEffect } from 'react'
import { ClockIcon, CalendarIcon } from '@heroicons/react/24/outline'
import { ModernInput } from '@/components/ModernInput'

interface CronPreset {
  label: string
  cron: string
  description: string
}

const CRON_PRESETS: CronPreset[] = [
  { label: 'Every hour', cron: '0 * * * *', description: 'At minute 0 of every hour' },
  { label: 'Every 6 hours', cron: '0 */6 * * *', description: 'At minute 0 every 6 hours' },
  { label: 'Every 12 hours', cron: '0 */12 * * *', description: 'At minute 0 every 12 hours' },
  { label: 'Daily at midnight', cron: '0 0 * * *', description: 'Every day at 00:00' },
  { label: 'Daily at 6 AM', cron: '0 6 * * *', description: 'Every day at 06:00' },
  { label: 'Weekly on Sunday', cron: '0 0 * * 0', description: 'Every Sunday at 00:00' },
  { label: 'Weekly on Monday', cron: '0 0 * * 1', description: 'Every Monday at 00:00' },
  { label: 'Monthly', cron: '0 0 1 * *', description: 'First day of every month at 00:00' },
]

interface CronBuilderProps {
  value: string
  onChange: (cron: string) => void
  error?: string
}

type ScheduleType = 'preset' | 'hourly' | 'daily' | 'weekly' | 'custom'

export default function CronBuilder({ value, onChange, error }: CronBuilderProps) {
  const [scheduleType, setScheduleType] = useState<ScheduleType>('preset')
  const [selectedPreset, setSelectedPreset] = useState<string>('')
  const [customCron, setCustomCron] = useState(value)

  // Hourly settings
  const [hourlyInterval, setHourlyInterval] = useState(1)

  // Daily settings
  const [dailyHour, setDailyHour] = useState(0)
  const [dailyMinute, setDailyMinute] = useState(0)

  // Weekly settings
  const [weeklyDay, setWeeklyDay] = useState(0)
  const [weeklyHour, setWeeklyHour] = useState(0)

  useEffect(() => {
    // Try to detect schedule type from value
    const preset = CRON_PRESETS.find((p) => p.cron === value)
    if (preset) {
      setScheduleType('preset')
      setSelectedPreset(preset.cron)
      return
    }

    // Try to parse as hourly
    const hourlyMatch = value.match(/^0 \*\/(\d+) \* \* \*$/)
    if (hourlyMatch) {
      setScheduleType('hourly')
      setHourlyInterval(parseInt(hourlyMatch[1]))
      return
    }

    // Try to parse as daily
    const dailyMatch = value.match(/^(\d+) (\d+) \* \* \*$/)
    if (dailyMatch) {
      setScheduleType('daily')
      setDailyMinute(parseInt(dailyMatch[1]))
      setDailyHour(parseInt(dailyMatch[2]))
      return
    }

    // Try to parse as weekly
    const weeklyMatch = value.match(/^(\d+) (\d+) \* \* (\d)$/)
    if (weeklyMatch) {
      setScheduleType('weekly')
      setDailyMinute(parseInt(weeklyMatch[1]))
      setWeeklyHour(parseInt(weeklyMatch[2]))
      setWeeklyDay(parseInt(weeklyMatch[3]))
      return
    }

    // Default to custom
    setScheduleType('custom')
    setCustomCron(value)
  }, [])

  const updateCron = () => {
    let newCron = value

    switch (scheduleType) {
      case 'preset':
        newCron = selectedPreset || '0 * * * *'
        break
      case 'hourly':
        newCron = hourlyInterval === 1 ? '0 * * * *' : `0 */${hourlyInterval} * * *`
        break
      case 'daily':
        newCron = `${dailyMinute} ${dailyHour} * * *`
        break
      case 'weekly':
        newCron = `0 ${weeklyHour} * * ${weeklyDay}`
        break
      case 'custom':
        newCron = customCron
        break
    }

    onChange(newCron)
  }

  useEffect(() => {
    updateCron()
  }, [scheduleType, selectedPreset, hourlyInterval, dailyHour, dailyMinute, weeklyDay, weeklyHour, customCron])

  const formatTime = (hour: number, minute: number = 0) => {
    return `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`
  }

  const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

  return (
    <div className="space-y-4">
      {/* Schedule Type Selection */}
      <div className="grid grid-cols-5 gap-2">
        {(['preset', 'hourly', 'daily', 'weekly', 'custom'] as ScheduleType[]).map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => setScheduleType(type)}
            className={`px-3 py-2 text-sm font-medium rounded-lg border transition-colors ${scheduleType === type
                ? 'bg-blue-600 text-white border-blue-600 dark:bg-blue-600 dark:border-blue-600'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-700'
              }`}
          >
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </button>
        ))}
      </div>

      {/* Preset Selection */}
      {scheduleType === 'preset' && (
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Select a preset schedule
          </label>
          <select
            value={selectedPreset}
            onChange={(e) => setSelectedPreset(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Choose a preset...</option>
            {CRON_PRESETS.map((preset) => (
              <option key={preset.cron} value={preset.cron}>
                {preset.label} - {preset.description}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Hourly Settings */}
      {scheduleType === 'hourly' && (
        <div className="flex items-center gap-3">
          <ClockIcon className="w-5 h-5 text-gray-400 dark:text-gray-500" />
          <span className="text-gray-700 dark:text-gray-300">Every</span>
          <select
            value={hourlyInterval}
            onChange={(e) => setHourlyInterval(parseInt(e.target.value))}
            className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-blue-500 focus:border-blue-500"
          >
            {[1, 2, 3, 4, 6, 8, 12].map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
          <span className="text-gray-700 dark:text-gray-300">hour(s)</span>
        </div>
      )}

      {/* Daily Settings */}
      {scheduleType === 'daily' && (
        <div className="flex items-center gap-3">
          <CalendarIcon className="w-5 h-5 text-gray-400 dark:text-gray-500" />
          <span className="text-gray-700 dark:text-gray-300">Every day at</span>
          <select
            value={dailyHour}
            onChange={(e) => setDailyHour(parseInt(e.target.value))}
            className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-blue-500 focus:border-blue-500"
          >
            {Array.from({ length: 24 }, (_, i) => (
              <option key={i} value={i}>
                {formatTime(i)}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Weekly Settings */}
      {scheduleType === 'weekly' && (
        <div className="flex items-center gap-3 flex-wrap">
          <CalendarIcon className="w-5 h-5 text-gray-400 dark:text-gray-500" />
          <span className="text-gray-700 dark:text-gray-300">Every</span>
          <select
            value={weeklyDay}
            onChange={(e) => setWeeklyDay(parseInt(e.target.value))}
            className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-blue-500 focus:border-blue-500"
          >
            {DAYS.map((day, i) => (
              <option key={i} value={i}>
                {day}
              </option>
            ))}
          </select>
          <span className="text-gray-700 dark:text-gray-300">at</span>
          <select
            value={weeklyHour}
            onChange={(e) => setWeeklyHour(parseInt(e.target.value))}
            className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-blue-500 focus:border-blue-500"
          >
            {Array.from({ length: 24 }, (_, i) => (
              <option key={i} value={i}>
                {formatTime(i)}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Custom Cron Expression */}
      {scheduleType === 'custom' && (
        <div className="space-y-2">
          <ModernInput
            label="Cron Expression"
            value={customCron}
            onChange={(e) => setCustomCron(e.target.value)}
            placeholder="* * * * *"
            error={error}
            helperText="Format: minute hour day month weekday (e.g., 0 */6 * * * for every 6 hours)"
            className="font-mono"
          />
        </div>
      )}

      {/* Current Value Display */}
      <div className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
        <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">Current schedule:</div>
        <div className="font-mono text-gray-900 dark:text-white">{value}</div>
      </div>
    </div>
  )
}
