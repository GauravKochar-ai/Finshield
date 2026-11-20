import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import './globals.css';
import { AuthProvider } from '@/lib/auth';
import { Shell } from '@/components/Shell';

export const metadata: Metadata = { title: 'FinShield AI · Security Operations', description: 'FinShield AI security operations console (synthetic demo data)' };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider><Shell>{children}</Shell></AuthProvider>
      </body>
    </html>
  );
}
