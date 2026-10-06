'use client';

import { ProtectedRoute } from '@/lib/protected-route';
import { DashboardLayout } from '@/components/dashboard/dashboard-layout';

export default function DashboardRoot({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute>
      <DashboardLayout>{children}</DashboardLayout>
    </ProtectedRoute>
  );
}
