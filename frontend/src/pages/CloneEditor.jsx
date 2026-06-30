import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiFetch } from '../api/client.js'

export default function CloneEditor() {
  const { cloneId } = useParams()
  const [clone, setClone] = useState(null)
  const [docs, setDocs] = useState([])
  const [conversations, setConversations] = useState([])
  const [gaps, setGaps] = useState([])
  const [docType, setDocType] = useState('resume')
  const [file, setFile] = useState(null)
  const [projectUrl, setProjectUrl] = useState('')
  const [editingText, setEditingText] = useState({})
  const [status, setStatus] = useState('')

  async function loadAll() {
    setClone(await apiFetch(`/clones/${cloneId}`))
    setDocs(await apiFetch(`/documents/clone/${cloneId}`))
    setConversations(await apiFetch(`/clones/${cloneId}/conversations`))
    setGaps(await apiFetch(`/clones/${cloneId}/gaps`))
  }

  useEffect(() => { loadAll() }, [cloneId])

  async function uploadFile(e) {
    e.preventDefault()
    if (!file) return
    setStatus('Uploading & parsing...')
    const form = new FormData()
    form.append('clone_id', cloneId)
    form.append('doc_type', docType)
    form.append('file', file)
    try {
      await apiFetch('/documents/upload', { method: 'POST', body: form, isForm: true })
      setFile(null)
      setStatus('Uploaded. Review the extracted content below before confirming.')
      loadAll()
    } catch (err) {
      setStatus('Error: ' + err.message)
    }
  }

  async function addProjectLink(e) {
    e.preventDefault()
    if (!projectUrl) return
    setStatus('Fetching link...')
    try {
      await apiFetch('/documents/project-link', { method: 'POST', body: { clone_id: Number(cloneId), url: projectUrl } })
      setProjectUrl('')
      setStatus('Link added. Review the extracted content below before confirming.')
      loadAll()
    } catch (err) {
      setStatus('Error: ' + err.message)
    }
  }

  async function confirmDoc(docId) {
    const text = editingText[docId]
    await apiFetch(`/documents/${docId}/confirm`, { method: 'POST', body: { confirmed_text: text } })
    loadAll()
  }

  async function deleteDoc(docId) {
    await apiFetch(`/documents/${docId}`, { method: 'DELETE' })
    loadAll()
  }

  async function generateClone() {
    setStatus('Generating clone (chunking + embedding confirmed documents)...')
    try {
      const res = await apiFetch(`/clones/${cloneId}/generate`, { method: 'POST' })
      setStatus(`Clone generated — ${res.chunks_indexed} chunks indexed.`)
    } catch (err) {
      setStatus('Error: ' + err.message)
    }
  }

  async function publish() {
    const res = await apiFetch(`/clones/${cloneId}/publish`, { method: 'POST' })
    setStatus(`Published! Public link: /c/${res.public_slug}`)
    loadAll()
  }

  async function unpublish() {
    await apiFetch(`/clones/${cloneId}/unpublish`, { method: 'POST' })
    loadAll()
  }

  if (!clone) return <div className="container">Loading...</div>

  return (
    <div className="container">
      <h1>{clone.name}</h1>
      <p>{status}</p>

      <div className="card">
        <h3>1. Upload source documents</h3>
        <form onSubmit={uploadFile}>
          <label>Document type</label>
          <select value={docType} onChange={(e) => setDocType(e.target.value)}>
            <option value="resume">Resume (PDF/DOCX)</option>
            <option value="linkedin">LinkedIn export (PDF)</option>
            <option value="certificate">Certificate (PDF/JPG/PNG)</option>
          </select>
          <label>File</label>
          <input type="file" onChange={(e) => setFile(e.target.files[0])} />
          <button type="submit">Upload</button>
        </form>

        <form onSubmit={addProjectLink} style={{ marginTop: 16 }}>
          <label>Or add a project link (GitHub / portfolio URL)</label>
          <input value={projectUrl} onChange={(e) => setProjectUrl(e.target.value)} placeholder="https://github.com/you/project" />
          <button type="submit">Add link</button>
        </form>
      </div>

      <div className="card">
        <h3>2. Review & confirm extracted content</h3>
        {docs.length === 0 && <p>No documents yet.</p>}
        {docs.map((d) => (
          <div key={d.id} style={{ borderTop: '1px solid #eee', paddingTop: 12, marginTop: 12 }}>
            <p><strong>{d.doc_type}</strong> — {d.original_filename || d.source_url} {' '}
              {d.confirmed ? <span className="badge">confirmed</span> : <span className="badge warn">needs review</span>}
            </p>
            <textarea
              rows={6}
              defaultValue={d.confirmed_text || d.raw_extracted_text || ''}
              onChange={(e) => setEditingText((s) => ({ ...s, [d.id]: e.target.value }))}
            />
            <button onClick={() => confirmDoc(d.id)}>Confirm content</button>{' '}
            <button className="secondary" onClick={() => deleteDoc(d.id)}>Delete</button>
          </div>
        ))}
      </div>

      <div className="card">
        <h3>3. Generate & publish</h3>
        <button onClick={generateClone}>Generate / re-generate clone</button>{' '}
        {!clone.published ? (
          <button onClick={publish}>Publish clone</button>
        ) : (
          <button className="secondary" onClick={unpublish}>Unpublish</button>
        )}
        {clone.published && clone.public_slug && (
          <p style={{ marginTop: 8 }}>
            Public link: <a href={`/c/${clone.public_slug}`} target="_blank" rel="noreferrer">/c/{clone.public_slug}</a>
          </p>
        )}
      </div>

      <div className="card">
        <h3>Visitor conversations</h3>
        {conversations.length === 0 && <p>No conversations yet.</p>}
        {conversations.map((c) => (
          <div key={c.id} style={{ borderTop: '1px solid #eee', paddingTop: 8, marginTop: 8 }}>
            <p><em>{c.visitor_name || 'Anonymous visitor'}</em> — {new Date(c.created_at).toLocaleString()}</p>
            {c.messages.map((m) => (
              <div key={m.id} className={`chat-bubble ${m.role === 'visitor' ? 'visitor' : 'clone'}`}>
                {m.content}
                {m.role === 'clone' && (
                  <button
                    className="secondary"
                    style={{ display: 'block', marginTop: 6, fontSize: 11 }}
                    onClick={async () => {
                      const correction = prompt('Correction for this answer:')
                      if (correction) {
                        await apiFetch(`/clones/messages/${m.id}/flag`, { method: 'POST', body: { correction } })
                        alert('Flagged.')
                      }
                    }}
                  >
                    Flag as inaccurate
                  </button>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="card">
        <h3>Knowledge gaps (questions your clone couldn't answer)</h3>
        {gaps.length === 0 && <p>No gaps recorded yet.</p>}
        <ul>
          {gaps.map((g) => <li key={g.id}>{g.content}</li>)}
        </ul>
      </div>
    </div>
  )
}
