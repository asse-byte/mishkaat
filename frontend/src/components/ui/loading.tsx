import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function LoadingSpinner({ className, size = 'md' }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  return (
    <div className={cn('flex items-center justify-center', className)}>
      <div
        className={cn(
          'animate-spin rounded-full border-2 border-[hsl(var(--muted))] border-t-[hsl(var(--primary))]',
          sizeClasses[size]
        )}
      />
    </div>
  );
}

export function LoadingPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[hsl(var(--background))]">
      <div className="text-center">
        <LoadingSpinner size="lg" className="mb-4" />
        <p className="text-[hsl(var(--muted-foreground))]">جاري التحميل...</p>
      </div>
    </div>
  );
}
