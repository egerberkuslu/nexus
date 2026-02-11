import { Fragment } from 'react'
import { Listbox, Transition } from '@headlessui/react'
import { CheckIcon, ChevronUpDownIcon } from '@heroicons/react/20/solid'
import { cn } from '@/utils/cn'

export type SelectOption<T extends string | number> = {
  value: T
  label: string
  description?: string
  disabled?: boolean
}

export type SelectProps<T extends string | number> = {
  label?: string
  value: T
  onChange: (value: T) => void
  options: SelectOption<T>[]
  placeholder?: string
  error?: string
  helperText?: string
  disabled?: boolean
  className?: string
}

export function Select<T extends string | number>({
  label,
  value,
  onChange,
  options,
  placeholder = 'Select…',
  error,
  helperText,
  disabled,
  className,
}: SelectProps<T>) {
  const selected = options.find((o) => o.value === value) || null

  return (
    <div className={cn('w-full', className)}>
      {label ? <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{label}</label> : null}

      <Listbox value={value} onChange={onChange} disabled={disabled}>
        <div className="relative">
          <Listbox.Button
            className={cn(
              'relative w-full cursor-pointer rounded-xl border px-4 py-2 pr-10 text-left transition-all duration-200',
              'bg-white dark:bg-gray-800',
              'text-gray-900 dark:text-gray-100',
              'focus:outline-none focus:ring-2',
              error
                ? 'border-red-300 dark:border-red-700 focus:ring-red-500 dark:focus:ring-red-400'
                : 'border-gray-300 dark:border-gray-600 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent',
              disabled && 'opacity-50 cursor-not-allowed'
            )}
          >
            <span className="block truncate text-sm">
              {selected ? selected.label : placeholder}
            </span>
            <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 dark:text-gray-500">
              <ChevronUpDownIcon className="h-5 w-5" aria-hidden="true" />
            </span>
          </Listbox.Button>

          <Transition
            as={Fragment}
            leave="transition ease-in duration-100"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
            enter="transition ease-out duration-100"
            enterFrom="opacity-0 translate-y-1"
            enterTo="opacity-100 translate-y-0"
          >
            <Listbox.Options className="absolute z-20 mt-2 max-h-72 w-full overflow-auto rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 py-1 shadow-lg focus:outline-none">
              {options.map((opt) => (
                <Listbox.Option
                  key={String(opt.value)}
                  value={opt.value}
                  disabled={opt.disabled}
                  className={({ active, disabled: optDisabled }) =>
                    cn(
                      'relative cursor-pointer select-none px-4 py-2',
                      optDisabled && 'opacity-50 cursor-not-allowed',
                      active ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                    )
                  }
                >
                  {({ selected: isSelected }) => (
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className={cn('truncate text-sm', isSelected ? 'font-semibold text-gray-900 dark:text-gray-100' : 'text-gray-800 dark:text-gray-200')}>
                          {opt.label}
                        </div>
                        {opt.description ? (
                          <div className="mt-0.5 truncate text-[11px] text-gray-500 dark:text-gray-400">{opt.description}</div>
                        ) : null}
                      </div>
                      {isSelected ? (
                        <span className="mt-0.5 text-blue-600 dark:text-blue-400">
                          <CheckIcon className="h-5 w-5" aria-hidden="true" />
                        </span>
                      ) : null}
                    </div>
                  )}
                </Listbox.Option>
              ))}
            </Listbox.Options>
          </Transition>
        </div>
      </Listbox>

      {error ? <p className="mt-1 text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      {helperText && !error ? <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{helperText}</p> : null}
    </div>
  )
}

