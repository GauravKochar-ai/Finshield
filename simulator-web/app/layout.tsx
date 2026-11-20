import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import './globals.css';
import { AuthProvider } from '@/lib/auth';
import { Gate } from '@/components/Gate';

export const metadata: Metadata = { title: 'FinShield Simulator', description: 'Scenario simulator for FinShield (synthetic data only)' };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en"><body><AuthProvider><Gate>{children}</Gate></AuthProvider></body></html>
  );
}
