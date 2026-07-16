import { StrictMode, useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const api = async (path, options = {}) => {
  const response = await fetch(path, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || `请求失败（${response.status}）`)
  return data
}

function App() {
  const [knowledgeBases, setKnowledgeBases] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [documents, setDocuments] = useState([])
  const [messages, setMessages] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('')
  const fileRef = useRef(null)

  const loadKnowledgeBases = async () => {
    const data = await api('/api/knowledge-bases')
    setKnowledgeBases(data)
    if (!selectedId && data.length) setSelectedId(data[0].id)
  }

  const loadDocuments = async (id) => {
    if (!id) return
    setDocuments(await api(`/api/knowledge-bases/${id}/documents`))
  }

  useEffect(() => { loadKnowledgeBases().catch(error => setNotice(error.message)) }, [])
  useEffect(() => { loadDocuments(selectedId).catch(error => setNotice(error.message)) }, [selectedId])

  const createKnowledgeBase = async () => {
    const name = window.prompt('知识库名称')
    if (!name?.trim()) return
    try {
      const item = await api('/api/knowledge-bases', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name: name.trim(), description: '' })
      })
      setKnowledgeBases(current => [item, ...current])
      setSelectedId(item.id)
      setMessages([])
      setConversationId(null)
    } catch (error) { setNotice(error.message) }
  }

  const upload = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || !selectedId) return
    setLoading(true); setNotice('正在解析文档并建立向量索引，首次运行可能需要下载模型…')
    try {
      const form = new FormData(); form.append('file', file)
      await api(`/api/knowledge-bases/${selectedId}/documents`, { method: 'POST', body: form })
      await loadDocuments(selectedId)
      setNotice(`已加入：${file.name}`)
    } catch (error) { setNotice(error.message) } finally { setLoading(false) }
  }

  const importWebpage = async () => {
    if (!selectedId) return
    const url = window.prompt('输入网页地址')
    if (!url?.trim()) return
    setLoading(true); setNotice('正在抓取网页正文并建立索引…')
    try {
      await api(`/api/knowledge-bases/${selectedId}/webpages`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ url: url.trim() })
      })
      await loadDocuments(selectedId); setNotice('网页已加入知识库')
    } catch (error) { setNotice(error.message) } finally { setLoading(false) }
  }

  const summarize = async () => {
    if (!selectedId || loading) return
    setLoading(true); setNotice('正在生成带引用的知识库总结…')
    try {
      const result = await api(`/api/knowledge-bases/${selectedId}/summarize`, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})
      })
      setConversationId(result.conversation_id)
      setMessages(current => [...current, { role: 'assistant', content: result.answer, citations: result.citations }])
      setNotice('总结已生成')
    } catch (error) { setNotice(error.message) } finally { setLoading(false) }
  }

  const ask = async (event) => {
    event.preventDefault()
    const text = question.trim()
    if (!text || !selectedId || loading) return
    setQuestion(''); setLoading(true)
    setMessages(current => [...current, { role: 'user', content: text }])
    try {
      const result = await api(`/api/knowledge-bases/${selectedId}/query`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ question: text, top_k: 5, conversation_id: conversationId })
      })
      setConversationId(result.conversation_id)
      setMessages(current => [...current, { role: 'assistant', content: result.answer, citations: result.citations }])
    } catch (error) {
      setMessages(current => [...current, { role: 'assistant', content: `请求失败：${error.message}` }])
    } finally { setLoading(false) }
  }

  const selected = knowledgeBases.find(item => item.id === selectedId)

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">K</div><div><strong>Knowledge Agent</strong><small>Private research workspace</small></div></div>
      <div className="side-heading"><span>知识库</span><button className="icon-button" onClick={createKnowledgeBase}>＋</button></div>
      <div className="kb-list">
        {knowledgeBases.map(item => <button key={item.id} className={`kb-item ${selectedId === item.id ? 'active' : ''}`} onClick={() => { setSelectedId(item.id); setMessages([]); setConversationId(null) }}><span className="kb-dot" />{item.name}</button>)}
        {!knowledgeBases.length && <div className="empty-side">还没有知识库<br /><button onClick={createKnowledgeBase}>创建第一个</button></div>}
      </div>
      <div className="sidebar-foot"><span className="status-dot" />本地工作区<br /><small>资料不会自动上传训练</small></div>
    </aside>
    <main className="content">
      <header className="topbar"><div><div className="eyebrow">PERSONAL KNOWLEDGE AGENT</div><h1>{selected?.name || '选择一个知识库'}</h1><p>{selected?.description || '上传资料，开始基于证据的检索问答。'}</p></div><div className="top-actions"><button className="secondary" onClick={summarize} disabled={!selectedId || loading}>生成总结</button><button className="secondary" onClick={importWebpage} disabled={!selectedId || loading}>导入网页</button><button className="secondary" onClick={() => loadDocuments(selectedId)}>刷新文档</button><label className="primary"><span>＋ 上传资料</span><input ref={fileRef} type="file" accept=".pdf,.docx,.md,.txt" onChange={upload} disabled={!selectedId || loading} /></label></div></header>
      {notice && <div className="notice">{notice}</div>}
      <section className="workspace">
        <div className="chat-card">
          <div className="card-head"><div><h2>知识库问答</h2><span>回答将优先依据已上传文档，并保留页码引用</span></div><span className="pill">{documents.length} 个文档</span></div>
          <div className="messages">
            {!messages.length && <div className="welcome"><div className="welcome-icon">✦</div><h3>从资料中找到答案</h3><p>你可以询问方法、结论、定义、合同条款，或比较多个文档的观点。</p><div className="suggestions"><button onClick={() => setQuestion('请总结这些文档的核心观点')}>总结核心观点</button><button onClick={() => setQuestion('这些资料中使用了哪些方法？')}>提取研究方法</button><button onClick={() => setQuestion('请列出相关结论及其页码')}>查找关键结论</button></div></div>}
            {messages.map((message, index) => <div key={index} className={`message ${message.role}`}><div className="avatar">{message.role === 'user' ? '我' : '✦'}</div><div className="bubble"><div className="message-content">{message.content}</div>{message.citations?.length > 0 && <div className="citations"><div className="citation-title">证据来源</div>{message.citations.map((citation, i) => <div className="citation" key={citation.chunk_id || i}><span className="citation-index">[{i + 1}]</span><div><strong>{citation.filename}</strong><span>第 {citation.page_number} 页 · 相似度 {citation.score}</span><p>{citation.quote}</p></div></div>)}</div>}</div></div>)}
            {loading && <div className="typing"><span /><span /><span />正在处理…</div>}
          </div>
          <form className="composer" onSubmit={ask}><input value={question} onChange={event => setQuestion(event.target.value)} placeholder={selectedId ? '询问你的文档…' : '请先创建知识库'} disabled={!selectedId || loading} /><button className="send" disabled={!selectedId || loading || !question.trim()}>发送</button></form>
        </div>
        <aside className="documents-card"><div className="card-head"><div><h2>文档</h2><span>当前知识库中的资料</span></div></div><div className="document-list">{documents.map(document => <div className="document" key={document.id}><div className="file-icon">{document.source_type === 'webpage' ? 'WEB' : document.source_type.toUpperCase()}</div><div className="document-meta"><strong title={document.filename}>{document.filename}</strong><span>{document.source_type === 'pdf' ? `${document.page_count} 页` : document.source_type.toUpperCase()} · {document.status === 'INDEXED' ? '已建立索引' : document.status}{document.ocr_used ? ' · OCR' : ''}</span></div><span className="ready-dot" /></div>)}{!documents.length && <div className="empty-docs"><div>▧</div><p>还没有文档</p><small>支持 PDF、DOCX、MD 和 TXT</small></div>}</div></aside>
      </section>
    </main>
  </div>
}

createRoot(document.getElementById('root')).render(<StrictMode><App /></StrictMode>)
