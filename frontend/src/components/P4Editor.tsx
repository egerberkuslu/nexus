import { useRef, useEffect } from 'react'
import Editor, { Monaco } from '@monaco-editor/react'
import { editor } from 'monaco-editor'

interface P4EditorProps {
  value?: string
  onChange?: (value: string) => void
  onSave?: (value: string) => void | Promise<void>
  onCompile?: (value: string) => void | Promise<void>
  readOnly?: boolean
  height?: string
}

export const DEFAULT_P4_CODE = `/* P4_16 Example: Simple L2 Switch */

#include <core.p4>
#include <v1model.p4>

// Headers
header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

struct headers_t {
    ethernet_t ethernet;
}

struct metadata_t {
    // Add custom metadata here
}

// Parser
parser MyParser(
    packet_in packet,
    out headers_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t standard_metadata
) {
    state start {
        packet.extract(hdr.ethernet);
        transition accept;
    }
}

// Ingress Processing
control MyIngress(
    inout headers_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t standard_metadata
) {
    action forward(bit<9> port) {
        standard_metadata.egress_spec = port;
    }

    action drop() {
        mark_to_drop(standard_metadata);
    }

    table mac_table {
        key = {
            hdr.ethernet.dstAddr: exact;
        }
        actions = {
            forward;
            drop;
        }
        size = 1024;
        default_action = drop();
    }

    apply {
        if (hdr.ethernet.isValid()) {
            mac_table.apply();
        }
    }
}

// Egress Processing
control MyEgress(
    inout headers_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t standard_metadata
) {
    apply { }
}

// Checksum Verification
control MyVerifyChecksum(
    inout headers_t hdr,
    inout metadata_t meta
) {
    apply { }
}

// Checksum Computation
control MyComputeChecksum(
    inout headers_t hdr,
    inout metadata_t meta
) {
    apply { }
}

// Deparser
control MyDeparser(
    packet_out packet,
    in headers_t hdr
) {
    apply {
        packet.emit(hdr.ethernet);
    }
}

// Main Switch
V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;
`

export default function P4Editor({
  value = DEFAULT_P4_CODE,
  onChange,
  onSave,
  onCompile,
  readOnly = false,
  height = '600px',
}: P4EditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null)

  const handleEditorDidMount = (
    editor: editor.IStandaloneCodeEditor,
    monaco: Monaco
  ) => {
    editorRef.current = editor

    // Register P4 language if not already registered
    if (!monaco.languages.getLanguages().some((lang) => lang.id === 'p4')) {
      monaco.languages.register({ id: 'p4' })

      // P4 language configuration
      monaco.languages.setLanguageConfiguration('p4', {
        comments: {
          lineComment: '//',
          blockComment: ['/*', '*/'],
        },
        brackets: [
          ['{', '}'],
          ['[', ']'],
          ['(', ')'],
        ],
        autoClosingPairs: [
          { open: '{', close: '}' },
          { open: '[', close: ']' },
          { open: '(', close: ')' },
          { open: '"', close: '"' },
          { open: '<', close: '>' },
        ],
      })

      // P4 syntax highlighting
      monaco.languages.setMonarchTokensProvider('p4', {
        keywords: [
          'action',
          'actions',
          'apply',
          'bool',
          'bit',
          'const',
          'control',
          'default',
          'else',
          'enum',
          'error',
          'exit',
          'extern',
          'false',
          'header',
          'header_union',
          'if',
          'in',
          'inout',
          'int',
          'match_kind',
          'out',
          'package',
          'parser',
          'return',
          'select',
          'state',
          'struct',
          'switch',
          'table',
          'transition',
          'true',
          'tuple',
          'typedef',
          'varbit',
          'void',
          'pragma',
        ],

        typeKeywords: ['int', 'bit', 'bool', 'varbit', 'void', 'error'],

        operators: [
          '=',
          '>',
          '<',
          '!',
          '~',
          '?',
          ':',
          '==',
          '<=',
          '>=',
          '!=',
          '&&',
          '||',
          '++',
          '--',
          '+',
          '-',
          '*',
          '/',
          '&',
          '|',
          '^',
          '%',
          '<<',
          '>>',
          '>>>',
          '+=',
          '-=',
          '*=',
          '/=',
          '&=',
          '|=',
          '^=',
          '%=',
          '<<=',
          '>>=',
          '>>>=',
        ],

        symbols: /[=><!~?:&|+\-*\/\^%]+/,

        tokenizer: {
          root: [
            [
              /[a-z_$][\w$]*/,
              {
                cases: {
                  '@typeKeywords': 'keyword',
                  '@keywords': 'keyword',
                  '@default': 'identifier',
                },
              },
            ],
            [/[A-Z][\w\$]*/, 'type.identifier'],

            { include: '@whitespace' },

            [/[{}()\[\]]/, '@brackets'],
            [/[<>](?!@symbols)/, '@brackets'],
            [/@symbols/, { cases: { '@operators': 'operator', '@default': '' } }],

            [/\d*\.\d+([eE][\-+]?\d+)?/, 'number.float'],
            [/0[xX][0-9a-fA-F]+/, 'number.hex'],
            [/\d+/, 'number'],

            [/[;,.]/, 'delimiter'],

            [/"([^"\\]|\\.)*$/, 'string.invalid'],
            [/"/, { token: 'string.quote', bracket: '@open', next: '@string' }],
          ],

          comment: [
            [/[^\/*]+/, 'comment'],
            [/\/\*/, 'comment', '@push'],
            ['\\*/', 'comment', '@pop'],
            [/[\/*]/, 'comment'],
          ],

          string: [
            [/[^\\"]+/, 'string'],
            [/"/, { token: 'string.quote', bracket: '@close', next: '@pop' }],
          ],

          whitespace: [
            [/[ \t\r\n]+/, 'white'],
            [/\/\*/, 'comment', '@comment'],
            [/\/\/.*$/, 'comment'],
          ],
        },
      })
    }

    const getCurrentValue = () => editor.getValue()

    // Add P4 compile command
    editor.addAction({
      id: 'compile-p4',
      label: 'Compile P4 Program',
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
      run: () => {
        const code = getCurrentValue()
        if (onCompile) {
          void onCompile(code)
          return
        }
        console.log('Compile requested (no handler):', code)
      },
    })
  }

  const handleEditorChange = (value: string | undefined) => {
    if (onChange && value !== undefined) {
      onChange(value)
    }
  }

  return (
    <div className="h-full flex flex-col bg-gray-900 rounded-lg overflow-hidden">
      {/* Editor Toolbar */}
      <div className="bg-gray-800 border-b border-gray-700 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <span className="text-white font-medium">P4 Program Editor</span>
          <div className="flex items-center space-x-2 text-sm text-gray-400">
            <span>Language: P4_16</span>
            <span>•</span>
            <span>Target: BMv2</span>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <button
            className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
            type="button"
            onClick={() => {
              const code = editorRef.current?.getValue() ?? value
              if (onCompile) {
                void onCompile(code)
              } else {
                console.log('Compile requested (no handler):', code)
              }
            }}
          >
            Compile (Ctrl+Enter)
          </button>
          <button
            className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 text-sm"
            type="button"
            onClick={() => {
              const code = editorRef.current?.getValue() ?? value
              if (onSave) {
                void onSave(code)
              } else {
                console.log('Save requested (no handler)')
              }
            }}
          >
            Save
          </button>
          <button
            className="px-3 py-1 bg-gray-700 text-white rounded hover:bg-gray-600 text-sm"
            type="button"
          >
            Format
          </button>
        </div>
      </div>

      {/* Monaco Editor */}
      <div className="flex-1">
        <Editor
          height={height}
          defaultLanguage="p4"
          value={value}
          theme="vs-dark"
          options={{
            readOnly,
            minimap: { enabled: true },
            fontSize: 14,
            lineNumbers: 'on',
            rulers: [80, 120],
            wordWrap: 'off',
            automaticLayout: true,
            scrollBeyondLastLine: false,
            folding: true,
            renderWhitespace: 'selection',
            bracketPairColorization: { enabled: true },
            suggest: {
              showKeywords: true,
              showSnippets: true,
            },
          }}
          onMount={handleEditorDidMount}
          onChange={handleEditorChange}
        />
      </div>

      {/* Editor Footer */}
      <div className="bg-gray-800 border-t border-gray-700 px-4 py-2">
        <div className="flex items-center justify-between text-xs text-gray-400">
          <div className="flex items-center space-x-4">
            <span>Ln 1, Col 1</span>
            <span>UTF-8</span>
            <span>P4_16</span>
          </div>
          <div className="flex items-center space-x-2">
            <span>Ready</span>
          </div>
        </div>
      </div>
    </div>
  )
}
