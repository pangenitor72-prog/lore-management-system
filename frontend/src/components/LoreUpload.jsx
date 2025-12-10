import { useState } from 'react'
import './ChatInterface.css' // reuse basic styles

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:9000'

export default function LoreUpload() {
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('')
  const [processing, setProcessing] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) {
      setStatus('Please choose a file to upload.')
      return
    }

    setProcessing(true)
    setStatus('Uploading...')

    try {
      const formData = new FormData()
      formData.append('files', file)
      formData.append('process_immediately', 'true')

      const resp = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!resp.ok) {
        const text = await resp.text()
        throw new Error(text || `Upload failed with ${resp.status}`)
      }

      const json = await resp.json()
      setStatus(`Uploaded: ${JSON.stringify(json)}`)
      setFile(null)
    } catch (err) {
      console.error('Upload failed', err)
      setStatus(`Error: ${err.message}`)
    } finally {
      setProcessing(false)
    }
  }

  return (
    <div className="chat-interface">
      <header className="chat-header">
        <div className="chat-header__title">
          <span className="chat-header__icon">📤</span>
          <h1>Upload Lore</h1>
        </div>
      </header>

      <form className="chat-input-form" onSubmit={handleSubmit}>
        <div className="chat-input-wrapper">
          <input
            type="file"
            accept=".txt,.md,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            disabled={processing}
          />
          <button type="submit" className="chat-submit" disabled={processing}>
            <span>{processing ? 'Uploading...' : 'Upload'}</span>
          </button>
        </div>
      </form>

      {status && (
        <div className="chat-messages">
          <pre className="chat-debug-message">{status}</pre>
        </div>
      )}
    </div>
  )
}

