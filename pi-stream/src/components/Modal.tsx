import React, { ReactNode } from 'react';

interface ModalProps {
  onClose: () => void;
  children: ReactNode;
  title?: string;
  subtitle?: string;
}

const Modal: React.FC<ModalProps> = ({ onClose, children, title, subtitle }) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg relative w-[50vw] max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <button
            className="absolute top-4 right-4 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            onClick={onClose}
          >
            ✕
          </button>
          {title && <h3 className="text-lg font-semibold pr-8">{title}</h3>}
          {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
        </div>

        {/* Content */}
        <div className="p-4">
          {children}
        </div>
      </div>
    </div>
  );
};

export default Modal;