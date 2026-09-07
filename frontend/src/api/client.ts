import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL ?? '/api'

export const api = axios.create({ baseURL: BASE })

export interface Document {
  id: string
  filename: string
  file_size: number | null
  page_count: number | null
  status: string
  error_msg: string | null
  created_at: string
  updated_at: string
}

export interface Job {
  id: string
  doc_id: string
  status: string
  stage: string
  progress: number
  total_pages: number
  current_page: number
  message: string | null
  error_msg: string | null
  updated_at: string
}

export interface Chunk {
  id: string
  doc_id: string
  parent_id: string | null
  level: string
  page_num: number | null
  section_path: string | null
  raw_text: string
  source_type: string
  chunk_index: number
}

export const uploadDocument = async (file: File): Promise<{ doc_id: string; job_id: string; filename: string }> => {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/documents', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export const listDocuments = async (): Promise<Document[]> => {
  const { data } = await api.get('/documents')
  return data
}

export const getDocument = async (id: string): Promise<Document> => {
  const { data } = await api.get(`/documents/${id}`)
  return data
}

export const getJob = async (docId: string): Promise<Job> => {
  const { data } = await api.get(`/documents/${docId}/job`)
  return data
}

export const getChunks = async (docId: string, level?: string): Promise<Chunk[]> => {
  const { data } = await api.get(`/documents/${docId}/chunks`, {
    params: level ? { level } : {},
  })
  return data
}

export const subscribeToEvents = (
  docId: string,
  onEvent: (job: Job) => void,
  onDone: () => void,
): EventSource => {
  const es = new EventSource(`${BASE}/documents/${docId}/events`)
  es.onmessage = (e) => {
    const job: Job = JSON.parse(e.data)
    onEvent(job)
    if (job.status === 'done' || job.status === 'failed') {
      es.close()
      onDone()
    }
  }
  es.onerror = () => { es.close(); onDone() }
  return es
}
