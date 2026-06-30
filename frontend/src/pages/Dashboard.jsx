import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client.js'

export default function Dashboard() {
  const [clones, setClones] = useState([])
  const [name, setName] = useState('')
  const [roleTitle, setRoleTitle] = useState('')
  const [error, setError] = useState('')

  async function load() {
    try {
      setClones(await apiFetch('/clones'))
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [])

  async function createClone(e) {
    e.preventDefault()
    try {
      await apiFetch('/clones', { method: 'POST', body: { name, role_title: roleTitle } })
      setName(''); setRoleTitle('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function deleteAccount() {
    if (!confirm('Permanently delete your account and ALL data? This cannot be undone.')) return
    await apiFetch('/clones/account/me', { method: 'DELETE' })
    localStorage.removeItem('token')
    window.location.href = '/login'
  }

  return (
    <div className="container">
      <h1>Your Clones</h1>
      {error && <p style={{ color: 'crimson' }}>{error}</p>}

      <div className="card">
        <h3>Create a new clone</h3>
        <form onSubmit={createClone}>
          <label>Clone name (e.g., your full name)</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required />
          <label>Role / title</label>
          <input value={roleTitle} onChange={(e) => setRoleTitle(e.target.value)} placeholder="e.g., Backend Engineer" />
          <button type="submit">Create clone</button>
        </form>
      </div>

      {clones.map((c) => (
        <div className="card" key={c.id}>
          <h3>{c.name} {c.published ? <span className="badge">published</span> : <span className="badge warn">draft</span>}</h3>
          <p>{c.role_title}</p>
          <Link to={`/clones/${c.id}`}><button>Manage</button></Link>
          {c.published && c.public_slug && (
            <a href={`/c/${c.public_slug}`} target="_blank" rel="noreferrer" style={{ marginLeft: 12 }}>
              View public link →
            </a>
          )}
        </div>
      ))}

      <div className="card">
        <h3>Account</h3>
        <button className="secondary" onClick={deleteAccount}>Delete my account & all data (FR-4.5)</button>
      </div>
    </div>
  )
}
