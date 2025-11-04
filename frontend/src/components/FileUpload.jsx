/**
 * FileUpload 文件上传组件
 * 支持拖拽上传、进度显示
 */

import React, { useState, useRef } from 'react';
import { FolderOutlined, CloseOutlined } from '@ant-design/icons';
import apiService from '../services/api';
import './FileUpload.css';

const FileUpload = ({ onUploadComplete, onUploadError }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const fileInputRef = useRef(null);

  // 处理文件选择
  const handleFileSelect = (event) => {
    const files = Array.from(event.target.files);
    setSelectedFiles(files);
  };

  // 处理拖拽进入
  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  // 处理拖拽离开
  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  // 处理拖拽悬停
  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  // 处理文件放下
  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    setSelectedFiles(files);
  };

  // 上传文件
  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      alert('请先选择文件');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    try {
      // 调用 API 上传文件
      const result = await apiService.uploadFiles(
        selectedFiles,
        (progress) => {
          setUploadProgress(progress);
        }
      );

      // 上传成功
      if (onUploadComplete) {
        onUploadComplete(result.files, selectedFiles);
      }

      // 重置状态
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
      alert('上传失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setIsUploading(false);
    }
  };

  // 移除选中的文件
  const removeFile = (index) => {
    const newFiles = [...selectedFiles];
    newFiles.splice(index, 1);
    setSelectedFiles(newFiles);
  };

  // 格式化文件大小
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="file-upload-container">
      {/* 拖拽区域 */}
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
              ? '松开鼠标上传文件'
              : '点击或拖拽文件到此处上传'}
          </p>
          <p className="drop-zone-hint">
            支持 PDF、Word、Excel、PowerPoint、Markdown 等格式
          </p>
        </div>
      </div>

      {/* 已选文件列表 */}
      {selectedFiles.length > 0 && (
        <div className="selected-files">
          <h4>已选文件 ({selectedFiles.length})</h4>
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
                    title="移除"
                  >
                    <CloseOutlined />
                  </button>
                )}
              </li>
            ))}
          </ul>

          {/* 上传按钮 */}
          <button
            className="btn-upload"
            onClick={handleUpload}
            disabled={isUploading}
          >
            {isUploading ? '上传中...' : '开始上传'}
          </button>

          {/* 上传进度条 */}
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
