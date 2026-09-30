import React from 'react';

export const LoadingSkeleton = ({ className = "" }: { className?: string }) => (
  <div className={`animate-pulse bg-gray-700 rounded ${className}`} />
);

export const ErrorBoundary = ({ children }: { children: React.ReactNode }) => {
  // Simple error boundary implementation
  return <>{children}</>;
};
