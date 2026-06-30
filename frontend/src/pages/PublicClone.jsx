import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiFetch } from '../api/client.js'

export default function PublicClone() {
  const { slug } = useParams()
  const [clone, setClone] = useState(null)
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const [contactOpen, setContactOpen] = useState(false)
  const [visitorName, setVisitorName] = useState('')
  const [visitorEmail, setVisitorEmail] = useState('')

  useEffect(() => {
    (async () => {
      try {
        const c = await apiFetch(`/public/clone/${slug}`, { auth: false })
        setClone(c)
        const convo = await apiFetch(`/public/clone/${slug}/conversations`, {
          method: 'POST', body: {}, auth: false,
        })
        setConversationId(convo.conversation_id)
      } catch (err) {
        setError(err.message)
      }
    })()
  }, [slug])

  async function sendMessage(text) {
    if (!text.trim() || !conversationId) return
    setMessages((m) => [...m, { role: 'visitor', content: text }])
    setInput('')
    try {
      const res = await apiFetch(`/public/clone/${slug}/messages`, {
        method: 'POST',
        auth: false,
        body: { conversation_id: conversationId, message: text },
      })
      setMessages((m) => [...m, { role: 'clone', content: res.reply, sources: res.source_document_ids }])
    } catch (err) {
      setMessages((m) => [...m, { role: 'clone', content: '(error: ' + err.message + ')' }])
    }
  }

  async function shareContact(e) {
    e.preventDefault()
    // Opt-in only (FR-3.5) — simplest implementation: restart conversation with contact attached.
    await apiFetch(`/public/clone/${slug}/conversations`, {
      method: 'POST', auth: false, body: { visitor_name: visitorName, visitor_email: visitorEmail },
    }).then((c) => setConversationId(c.conversation_id))
    setContactOpen(false)
  }

  if (error) return <div className="container">{error}</div>
  if (!clone) return <div className="container">Loading...</div>

  return (
    <div className="container" style={{ maxWidth: 640 }}>
      <div className="card">
        <h2>{clone.name}</h2>
        <p>{clone.role_title}</p>
        <p>{clone.headline_summary}</p>
        <p style={{ fontSize: 12, color: '#666' }}>{clone.ai_disclosure}</p>
      </div>

      <div className="card">
        {messages.length === 0 && (
          <div style={{ marginBottom: 12 }}>
            <p>Try asking:</p>
            {clone.starter_questions.map((q) => (
              <button key={q} className="secondary" style={{ marginRight: 8, marginBottom: 8 }} onClick={() => sendMessage(q)}>
                {q}
              </button>
            ))}
          </div>
        )}

        <div>
          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble ${m.role}`}>
              {m.content}
              {m.role === 'clone' && m.sources && m.sources.length > 0 && (
                <div style={{ fontSize: 11, marginTop: 4, opacity: 0.7 }}>
                  Sourced from document(s): {m.sources.join(', ')}
                </div>
              )}
            </div>
          ))}
        </div>

        <form onSubmit={(e) => { e.preventDefault(); sendMessage(input) }} style={{ marginTop: 12 }}>
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask a question..." />
          <button type="submit">Send</button>
        </form>
      </div>

      <div className="card">
        {!contactOpen ? (
          <button className="secondary" onClick={() => setContactOpen(true)}>
            Leave your contact info (optional)
          </button>
        ) : (
          <form onSubmit={shareContact}>
            <label>Your name</label>
            <input value={visitorName} onChange={(e) => setVisitorName(e.target.value)} />
            <label>Your email</label>
            <input type="email" value={visitorEmail} onChange={(e) => setVisitorEmail(e.target.value)} />
            <button type="submit">Share</button>
          </form>
        )}
      </div>
    </div>
  )
}
