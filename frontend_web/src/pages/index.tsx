import { useRoutes } from 'react-router-dom';
import { Suspense } from 'react';
import { appRoutes } from '@/routesConfig';

const Pages = () => {
  const routing = useRoutes(appRoutes);
  return (
    <Suspense fallback={<div className="flex h-full items-center justify-center">Loading...</div>}>
      {routing}
    </Suspense>
  );
};

export default Pages;
