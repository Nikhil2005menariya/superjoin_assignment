import React, { useCallback, useState } from 'react'
import { UploadCloud } from 'lucide-react'
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
      toast.success(`"${filename}" uploaded`)
      onUploadStart(doc_id, filename)

      subscribeToEvents(
        doc_id,
        (job) => onJobUpdate(doc_id, job),
        () => { onUploadDone(doc_id); setUploading(false) },
      )
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? err.message ?? 'Upload failed')
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
        'flex flex-col items-center justify-center gap-5 rounded-lg border-2 border-dashed p-10 cursor-pointer transition-colors duration-150',
        dragging
          ? 'border-ink bg-stone'
          : 'border-hairline bg-canvas hover:border-slate',
        uploading && 'pointer-events-none opacity-50',
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

      <div className="flex h-12 w-12 items-center justify-center rounded-sm bg-stone">
        {uploading
          ? <div className="h-5 w-5 animate-spin rounded-full border-2 border-ink border-t-transparent" />
          : <UploadCloud className="h-5 w-5 text-ink" strokeWidth={1.5} />
        }
      </div>

      <div className="text-center">
        <p className="text-sm font-medium text-ink">
          {uploading ? 'Uploading…' : 'Drop a PDF or click to browse'}
        </p>
        <p className="mt-1 text-xs text-muted">
          Any document — reports, research, legal, filings
        </p>
        <p className="mt-1 text-xs text-muted">Max 200 MB · PDF only</p>
      </div>
    </label>
  )
}
