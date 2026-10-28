import { QueryClientProvider } from '@tanstack/react-query';
import App from '../App';
import { queryClient } from './queryClient';
import { TooltipProvider } from '../components/ui/Tooltip';

export default function Application() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider><App /></TooltipProvider>
    </QueryClientProvider>
  );
}
