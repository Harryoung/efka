/**
 * FileUpload Component
 * Supports drag & drop upload with progress display
 */

import React, { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { FolderOutlined, CloseOutlined } from '@ant-design/icons';
import apiService from '../services/api';
import './FileUpload.css';

const FileUpload = ({ onUploadComplete, onUploadError }) => {
  const { t } = useTranslation();
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const fileInputRef = useRef(null);

  const handleFileSelect = (event) => {
    const files = Array.from(event.target.files);
    setSelectedFiles(files);
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    setSelectedFiles(files);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      alert(t('upload.selectFirst'));
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    try {
      const result = await apiService.uploadFiles(
        selectedFiles,
        (progress) => {
          setUploadProgress(progress);
        }
      );

      if (onUploadComplete) {
        onUploadComplete(result.files, selectedFiles);
      }

      setSelectedFiles([]);
      setUploadProgress(0);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      console.error('Upload failed:', error);
      if (onUploadError) {
        onUploadError(error);
      }
      alert(`${t('upload.failed')}: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const removeFile = (index) => {
    const newFiles = [...selectedFiles];
    newFiles.splice(index, 1);
    setSelectedFiles(newFiles);
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="file-upload-container">
      {/* Drop zone */}
      <div
        className={`drop-zone ${isDragging ? 'dragging' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />

        <div className="drop-zone-content">
          <div className="upload-icon"><FolderOutlined /></div>
          <p className="drop-zone-text">
            {isDragging
              ? t('upload.dropHint')
              : t('upload.dragHint')}
          </p>
          <p className="drop-zone-hint">
            {t('upload.formatHint')}
          </p>
        </div>
      </div>

      {/* Selected files list */}
      {selectedFiles.length > 0 && (
        <div className="selected-files">
          <h4>{t('upload.selectedFiles')} ({selectedFiles.length})</h4>
          <ul className="file-list">
            {selectedFiles.map((file, index) => (
              <li key={index} className="file-item">
                <div className="file-info">
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">
                    {formatFileSize(file.size)}
                  </span>
                </div>
                {!isUploading && (
                  <button
                    className="btn-remove"
                    onClick={() => removeFile(index)}
                    title={t('upload.remove')}
                  >
                    <CloseOutlined />
                  </button>
                )}
              </li>
            ))}
          </ul>

          {/* Upload button */}
          <button
            className="btn-upload"
            onClick={handleUpload}
            disabled={isUploading}
          >
            {isUploading ? t('upload.uploading') : t('upload.startUpload')}
          </button>

          {/* Upload progress bar */}
          {isUploading && (
            <div className="upload-progress">
              <div
                className="progress-bar"
                style={{ width: `${uploadProgress}%` }}
              >
                <span className="progress-text">{uploadProgress}%</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default FileUpload;
