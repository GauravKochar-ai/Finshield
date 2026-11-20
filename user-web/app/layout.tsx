import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import './globals.css';
import { AuthProvider } from '@/lib/auth';
import { Gate } from '@/components/Gate';

export const metadata: Metadata = { title: 'FinLend Ops', description: 'FinLend Ops staff portal (SAMPLE data, monitored by FinShield)' };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en"><body><AuthProvider><Gate>{children}</Gate></AuthProvider></body></html>
  );
}
