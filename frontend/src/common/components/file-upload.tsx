'use client';

import { CircleAlertIcon, FileTextIcon, Trash2Icon, UploadIcon } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/reui/alert';
import { Badge } from '@/components/reui/badge';
import { formatBytes, useFileUpload } from '@/hooks/use-file-upload';

import { Button } from '@/common/components/ui/button';
import { cn } from '@/common/lib/utils';

interface FileUploadProps {
  accept?: string;
  maxSize?: number;
  disabled?: boolean;
  onFileSelected: (file: File | null) => void;
}

export function FileUpload({
  accept,
  maxSize = 50 * 1024 * 1024,
  disabled,
  onFileSelected,
}: FileUploadProps) {
  const [
    { files, isDragging, errors },
    { removeFile, handleDragEnter, handleDragLeave, handleDragOver, handleDrop, openFileDialog, getInputProps },
  ] = useFileUpload({
    maxFiles: 1,
    maxSize,
    accept,
    multiple: false,
    onFilesChange: (newFiles) => {
      const selected = newFiles[0]?.file;
      onFileSelected(selected instanceof File ? selected : null);
    },
  });

  const selectedFile = files[0];

  return (
    <div className="w-full space-y-3">
      <div
        className={cn(
          'relative rounded-lg border border-dashed p-6 text-center transition-colors',
          isDragging
            ? 'border-primary bg-primary/5'
            : 'border-muted-foreground/25 hover:border-muted-foreground/50',
          disabled && 'pointer-events-none opacity-50',
        )}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <input {...getInputProps()} className="sr-only" disabled={disabled} />
        <div className="flex flex-col items-center gap-3">
          <div
            className={cn(
              'bg-muted flex h-12 w-12 items-center justify-center rounded-full transition-colors',
              isDragging && 'bg-primary/10',
            )}
          >
            <UploadIcon className="text-muted-foreground h-5 w-5" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium">
              Drop a file here or{' '}
              <button
                type="button"
                onClick={openFileDialog}
                disabled={disabled}
                className="text-primary cursor-pointer underline-offset-4 hover:underline"
              >
                browse
              </button>
            </p>
            <p className="text-muted-foreground text-xs">
              1 file at a time · Maximum file size: {formatBytes(maxSize)}
            </p>
          </div>
        </div>
      </div>

      {selectedFile && (
        <div className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2">
          <div className="flex min-w-0 items-center gap-2">
            <FileTextIcon className="text-muted-foreground size-4 shrink-0" />
            <span className="truncate text-sm font-medium">{selectedFile.file.name}</span>
            <Badge variant="secondary" className="shrink-0 text-xs">
              {formatBytes(selectedFile.file.size)}
            </Badge>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8 shrink-0"
            disabled={disabled}
            onClick={() => removeFile(selectedFile.id)}
          >
            <Trash2Icon className="size-3.5" />
          </Button>
        </div>
      )}

      {errors.length > 0 && (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>File upload error</AlertTitle>
          <AlertDescription>
            {errors.map((error) => (
              <p key={error}>{error}</p>
            ))}
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
