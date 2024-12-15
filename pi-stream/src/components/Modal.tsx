import React, { ReactNode } from 'react';

interface ModalProps {
  onClose: () => void; // Function to close the modal
  children: ReactNode; // Content of the modal
}

const Modal: React.FC<ModalProps> = ({ onClose, children }) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-lg relative w-full max-w-3xl">
        <button 
          className="absolute top-2 right-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" 
          onClick={onClose}
        >
          ✕
        </button>
        {children}
      </div>
    </div>
  );
};

export default Modal;
