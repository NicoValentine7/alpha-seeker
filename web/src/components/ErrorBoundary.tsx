import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <tr>
          <td colSpan={99} className="px-6 py-4">
            <div className="bg-red-950/50 border border-red-800/50 rounded px-4 py-3 text-sm text-red-300">
              表示エラーが発生しました: {this.state.error?.message}
              <button
                onClick={() => this.setState({ hasError: false, error: null })}
                className="ml-3 text-red-400 hover:text-red-200 underline"
              >
                再試行
              </button>
            </div>
          </td>
        </tr>
      )
    }
    return this.props.children
  }
}
