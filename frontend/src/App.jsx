import { useState, useEffect, useRef } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8000/api'
const CHUNK_SIZE = 5 * 1024 * 1024 // 5MB per chunk

function App() {
  const [applicants, setApplicants] = useState([])
  const [selectedApplicant, setSelectedApplicant] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [logs, setLogs] = useState([])
  const [result, setResult] = useState(null)

  // Upload modal state
  const [showUpload, setShowUpload] = useState(false)
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadStatus, setUploadStatus] = useState('idle') // idle | uploading | success | error
  const [uploadedDatasets, setUploadedDatasets] = useState([])
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef(null)

  useEffect(() => {
    fetch(`${API_BASE}/sample-applicants`)
      .then(res => res.json())
      .then(data => { if (Array.isArray(data)) setApplicants(data) })
      .catch(err => console.error('Failed to load applicants', err))
  }, [])

  const fetchDatasets = async () => {
    try {
      const res = await fetch(`${API_BASE}/v1/dataset/list`)
      const data = await res.json()
      setUploadedDatasets(data.datasets || [])
    } catch (e) {
      console.error('Failed to fetch datasets', e)
    }
  }

  const handleOpenUpload = () => {
    setShowUpload(true)
    fetchDatasets()
  }

  const handleLoadDataset = async (key) => {
    try {
      const res = await fetch(`${API_BASE}/v1/dataset/load?key=${encodeURIComponent(key)}`)
      if (!res.ok) throw new Error("Failed to load dataset")
      const data = await res.json()
      if (Array.isArray(data)) {
        setApplicants(data)
        setSelectedApplicant(null)
        setResult(null)
        setLogs([])
        setShowUpload(false) // Close the modal
      }
    } catch (e) {
      console.error('Error loading dataset:', e)
      alert('Failed to load dataset from S3')
    }
  }

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true) }
  const handleDragLeave = () => setIsDragging(false)
  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) { setUploadFile(file); setUploadStatus('idle'); setUploadProgress(0) }
  }
  const handleFileSelect = (e) => {
    const file = e.target.files[0]
    if (file) { setUploadFile(file); setUploadStatus('idle'); setUploadProgress(0) }
  }

  // =============================================
  // MULTIPART S3 UPLOAD LOGIC
  // =============================================
  const handleUpload = async () => {
    if (!uploadFile) return
    setUploadStatus('uploading')
    setUploadProgress(0)

    let uploadId = null
    let key = null

    try {
      // Step 1: Initiate multipart upload — get upload_id from backend
      const initiateRes = await fetch(`${API_BASE}/v1/dataset/upload/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: uploadFile.name })
      })

      // ✅ Stop immediately if initiate fails (e.g. IAM permission denied)
      if (!initiateRes.ok) {
        const errData = await initiateRes.json()
        throw new Error(errData.detail || 'Failed to initiate upload')
      }

      const initiateData = await initiateRes.json()
      uploadId = initiateData.upload_id
      key = initiateData.key

      // Safety guard — ensure upload_id and key are present before continuing
      if (!uploadId || !key) {
        throw new Error('S3 initiate response missing upload_id or key')
      }


      // Step 2: Slice file into 5MB chunks and get presigned URLs for each
      const totalParts = Math.ceil(uploadFile.size / CHUNK_SIZE)
      const partNumbers = Array.from({ length: totalParts }, (_, i) => i + 1)

      const presignRes = await fetch(`${API_BASE}/v1/dataset/upload/presign-parts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ upload_id: uploadId, key, part_numbers: partNumbers })
      })
      const presignData = await presignRes.json()
      const presignedParts = presignData.parts // [{part_number, url}, ...]

      // Step 3: Upload each chunk directly to S3 using presigned PUT URLs
      const completedParts = []
      for (let i = 0; i < totalParts; i++) {
        const start = i * CHUNK_SIZE
        const end = Math.min(start + CHUNK_SIZE, uploadFile.size)
        const chunk = uploadFile.slice(start, end)

        const putRes = await fetch(presignedParts[i].url, {
          method: 'PUT',
          body: chunk,
          headers: { 'Content-Type': 'application/octet-stream' }
        })

        // ETag is required by S3 to assemble chunks into the final file
        const etag = putRes.headers.get('ETag')
        completedParts.push({ PartNumber: i + 1, ETag: etag })

        // Update progress bar
        setUploadProgress(Math.round(((i + 1) / totalParts) * 100))
      }

      // Step 4: Tell S3 to assemble all chunks into final file
      await fetch(`${API_BASE}/v1/dataset/upload/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ upload_id: uploadId, key, parts: completedParts })
      })

      setUploadStatus('success')
      fetchDatasets() // Refresh the dataset list

    } catch (err) {
      console.error('Upload failed:', err)
      setUploadStatus('error')
      // Abort orphaned multipart upload to avoid S3 storage charges
      if (uploadId && key) {
        await fetch(`${API_BASE}/v1/dataset/upload/abort?upload_id=${uploadId}&key=${encodeURIComponent(key)}`, {
          method: 'DELETE'
        })
      }
    }
  }

  const handleSelect = (app) => {
    setSelectedApplicant(app)
    setLogs([])
    setResult(null)
  }

  const runUnderwriting = async () => {
    if (!selectedApplicant) return
    setIsRunning(true)
    setLogs([{ type: 'info', msg: `Initializing AI Underwriting Pipeline for ${selectedApplicant.Name}...` }])
    setResult(null)
    try {
      setLogs(prev => [...prev, { type: 'info', msg: `Layer 1: Compliance Masking Active (ECOA Check)` }])
      setLogs(prev => [...prev, { type: 'info', msg: `Layer 2: Deterministic Router Evaluating Debt-to-Income...` }])
      const response = await fetch(`${API_BASE}/v1/underwrite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(selectedApplicant)
      })
      if (!response.ok) throw new Error(await response.text())
      const data = await response.json()
      setTimeout(() => setLogs(prev => [...prev, { type: 'info', msg: `Layer 3: Branch → ${data.execution_trace_summary.selected_route_track}` }]), 500)
      setTimeout(() => setLogs(prev => [...prev, { type: 'info', msg: `Layer 4: RAG Confidence → ${data.execution_trace_summary.rag_audit_confidence}` }]), 1000)
      setTimeout(() => {
        setLogs(prev => [...prev, { type: 'info', msg: `Layer 5: Auditor Score → ${data.execution_trace_summary.internal_eval_score}` }])
        if (data.execution_trace_summary.auto_remedy_executed)
          setLogs(prev => [...prev, { type: 'error', msg: `Layer 5: ⚠ Auto-Repair Triggered. Limit recalculated.` }])
      }, 1500)
      setTimeout(() => {
        setLogs(prev => [...prev, { type: 'success', msg: `Layer 6: Security Guardrail — Output Sanitized ✓` }])
        setResult(data.underwriting_decision_packet)
        setIsRunning(false)
      }, 2000)
    } catch (err) {
      setLogs(prev => [...prev, { type: 'error', msg: `Pipeline Error: ${err.message}` }])
      setIsRunning(false)
    }
  }

  return (
    <div className="app-container">

      {/* ===== UPLOAD MODAL ===== */}
      {showUpload && (
        <div className="modal-overlay" onClick={() => setShowUpload(false)}>
          <div className="modal-panel glass-panel" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>📂 Upload Dataset to S3</h2>
              <button className="modal-close" onClick={() => setShowUpload(false)}>✕</button>
            </div>

            {/* Drag & Drop Zone */}
            <div
              className={`drop-zone ${isDragging ? 'dragging' : ''} ${uploadFile ? 'has-file' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current.click()}
            >
              <input ref={fileInputRef} type="file" accept=".csv,.xlsx" hidden onChange={handleFileSelect} />
              {uploadFile ? (
                <div>
                  <div className="drop-icon">📄</div>
                  <div className="drop-filename">{uploadFile.name}</div>
                  <div className="drop-filesize">{(uploadFile.size / (1024 * 1024)).toFixed(2)} MB</div>
                </div>
              ) : (
                <div>
                  <div className="drop-icon">☁️</div>
                  <div className="drop-label">Drag & drop .csv or .xlsx here</div>
                  <div className="drop-sub">or click to browse</div>
                </div>
              )}
            </div>

            {/* Progress Bar */}
            {uploadStatus === 'uploading' && (
              <div className="progress-container">
                <div className="progress-label">
                  Uploading chunks to S3... {uploadProgress}%
                </div>
                <div className="progress-track">
                  <div className="progress-bar" style={{ width: `${uploadProgress}%` }} />
                </div>
                <div className="progress-sub">
                  Chunk {Math.ceil((uploadProgress / 100) * Math.ceil((uploadFile?.size || 0) / CHUNK_SIZE))} of {Math.ceil((uploadFile?.size || 0) / CHUNK_SIZE)} • {CHUNK_SIZE / (1024*1024)}MB per chunk
                </div>
              </div>
            )}

            {uploadStatus === 'success' && (
              <div className="upload-success">✅ File successfully uploaded to S3!</div>
            )}
            {uploadStatus === 'error' && (
              <div className="upload-error">❌ Upload failed. Aborted orphaned chunks from S3.</div>
            )}

            {/* Action Buttons */}
            <div className="modal-actions">
              <button
                className="glass-button"
                disabled={!uploadFile || uploadStatus === 'uploading'}
                onClick={handleUpload}
              >
                {uploadStatus === 'uploading' ? `Uploading ${uploadProgress}%...` : '⬆ Upload to S3'}
              </button>
            </div>

            {/* Previously Uploaded Datasets */}
            {uploadedDatasets.length > 0 && (
              <div className="dataset-list">
                <h4>Previously Uploaded Datasets</h4>
                {uploadedDatasets.map((ds, i) => (
                  <div key={i} className="dataset-item">
                    <div>
                      <div className="dataset-name">📊 {ds.filename}</div>
                      <div className="dataset-meta">{ds.size_mb} MB • {new Date(ds.last_modified).toLocaleDateString()}</div>
                    </div>
                    <button 
                      className="glass-button" 
                      style={{ padding: '0.4rem 0.8rem', minWidth: 'auto', fontSize: '0.85rem' }}
                      onClick={() => handleLoadDataset(ds.key)}
                    >
                      Load
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ===== SIDEBAR ===== */}
      <div className="sidebar glass-panel animate-fade-in">
        <div className="header-title">Terminator AI</div>

        <button className="upload-btn" onClick={handleOpenUpload}>
          ☁️ Upload Dataset
        </button>

        <h3 style={{ color: 'var(--text-secondary)', marginTop: '1rem' }}>Applicant Queue</h3>
        <div className="queue-list">
          {applicants.map((app, idx) => (
            <div
              key={idx}
              className={`applicant-card ${selectedApplicant?.Customer_ID === app.Customer_ID ? 'active' : ''}`}
              onClick={() => handleSelect(app)}
            >
              <div className="applicant-name">{app.Name || 'Unknown'}</div>
              <div className="applicant-meta">
                <span>Score: {app.Credit_Score}</span>
                <span>DTI: {((app.Outstanding_Debt / (app.Annual_Income || 1)) * 100).toFixed(1)}%</span>
              </div>
              <div className="applicant-meta" style={{ marginTop: '4px' }}>
                <span style={{ color: '#fbbf24' }}>{app.Highest_Risk_Type}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ===== MAIN PANEL ===== */}
      <div className="main-content">
        <div className="dashboard-panel glass-panel animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <div className="panel-header">
            <h2>{selectedApplicant ? `Processing: ${selectedApplicant.Name}` : 'Select an Applicant'}</h2>
            <button className="glass-button" onClick={runUnderwriting} disabled={!selectedApplicant || isRunning}>
              {isRunning ? 'Underwriting...' : 'Execute AI Pipeline'}
            </button>
          </div>

          <div className="metrics-grid">
            <div className="metric-box">
              <div className="metric-label">Annual Income</div>
              <div className="metric-value">${selectedApplicant?.Annual_Income?.toLocaleString() || '---'}</div>
            </div>
            <div className="metric-box">
              <div className="metric-label">Outstanding Debt</div>
              <div className="metric-value">${selectedApplicant?.Outstanding_Debt?.toLocaleString() || '---'}</div>
            </div>
            <div className="metric-box">
              <div className="metric-label">Credit Score</div>
              <div className="metric-value">{selectedApplicant?.Credit_Score || '---'}</div>
            </div>
            <div className="metric-box">
              <div className="metric-label">Risk Profile</div>
              <div className="metric-value">{selectedApplicant?.Highest_Risk_Type || '---'}</div>
            </div>
          </div>

          <h3 style={{ marginBottom: '1rem', color: 'var(--text-secondary)' }}>Pipeline Trace Log</h3>
          <div className="trace-log">
            {logs.map((log, i) => (
              <div key={i} className={`trace-line ${log.type}`}>
                <span style={{ opacity: 0.5 }}>[{new Date().toISOString().split('T')[1].slice(0, 8)}]</span> {log.msg}
              </div>
            ))}
            {isRunning && <div className="trace-line info">Processing...</div>}
          </div>

          {result && (
            <div className="decision-card animate-fade-in">
              <div className={`decision-status status-${result.status?.toLowerCase()}`}>{result.status}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
                <div>
                  <div className="metric-label">Recommended Product</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{result.card_product || result.tier}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div className="metric-label">Approved Credit Limit</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--accent-color)' }}>
                    ${result.credit_limit?.toLocaleString()}
                  </div>
                </div>
              </div>
              <div className="metric-label" style={{ marginBottom: '0.5rem' }}>Applied Disclosures / Perks</div>
              <div style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                {result.disclosure_applied || (Array.isArray(result.perks) ? result.perks.join(' • ') : '')}
              </div>

              <div style={{ marginTop: '2rem', borderTop: '1px solid var(--glass-border)', paddingTop: '1rem', textAlign: 'center' }}>
                <a 
                  href="https://smith.langchain.com/o/default/projects" 
                  target="_blank" 
                  rel="noreferrer"
                  className="glass-button"
                  style={{ display: 'inline-block', textDecoration: 'none', background: 'rgba(99, 102, 241, 0.2)' }}
                >
                  🔍 View Execution Trace in LangSmith
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default App
