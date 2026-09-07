import React, { useCallback, useState } from 'react'
import { UploadCloud, FileText, AlertCircle } from 'lucide-react'
import clsx from 'clsx'
import toast from 'react-hot-toast'
import { uploadDocument, subscribeToEvents, Job } from '../api/client'

interface Props {
  onUploadStart: (docId: string, filename: string) => void
  onJobUpdate: (docId: string, job: Job) => void
  onUploadDone: (docId: string) => void
}

export function UploadZone({ onUploadStart, onJobUpdate, onUploadDone }: Props) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)

  const handleFile = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      toast.error('Only PDF files are supported')
      return
    }
    if (file.size > 200 * 1024 * 1024) {
      toast.error('File exceeds 200 MB limit')
      return
    }

    setUploading(true)
    try {
      const { doc_id, filename } = await uploadDocument(file)
      toast.success(`"${filename}" uploaded — processing started`)
      onUploadStart(doc_id, filename)

      subscribeToEvents(
        doc_id,
        (job) => onJobUpdate(doc_id, job),
        () => {
          onUploadDone(doc_id)
          setUploading(false)
        },
      )
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err.message ?? 'Upload failed'
      toast.error(msg)
      setUploading(false)
    }
  }, [onUploadStart, onJobUpdate, onUploadDone])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const onInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }, [handleFile])

  return (
    <label
      htmlFor="pdf-upload"
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={clsx(
        'flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-10 cursor-pointer transition-all duration-200',
        dragging
          ? 'border-brand-500 bg-brand-50 scale-[1.01]'
          : 'border-gray-300 bg-white hover:border-brand-400 hover:bg-gray-50',
        uploading && 'pointer-events-none opacity-60',
      )}
    >
      <input
        id="pdf-upload"
        type="file"
        accept=".pdf"
        className="sr-only"
        onChange={onInputChange}
        disabled={uploading}
      />

      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-100">
        {uploading ? (
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
        ) : (
          <UploadCloud className="h-8 w-8 text-brand-600" />
        )}
      </div>

      <div className="text-center">
        <p className="text-base font-semibold text-gray-700">
          {uploading ? 'Uploading…' : 'Drop a PDF here or click to browse'}
        </p>
        <p className="mt-1 text-sm text-gray-500">
          Any PDF — financial reports, research papers, legal docs, etc.
        </p>
        <p className="mt-1 text-xs text-gray-400">Max 200 MB</p>
      </div>

      <div className="flex items-center gap-2 rounded-lg bg-amber-50 px-4 py-2 text-xs text-amber-700">
        <AlertCircle className="h-3.5 w-3.5 shrink-0" />
        Phase 1: Document intelligence — chunking &amp; table extraction
      </div>
    </label>
  )
}
