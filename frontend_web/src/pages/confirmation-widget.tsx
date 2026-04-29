import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { useChatContext } from '@/components/block/chat';

interface ConfirmationWidgetProps {
  message: string;
}

export function ConfirmationWidget({ message }: ConfirmationWidgetProps) {
  const { sendMessage, state } = useChatContext();
  console.log('state', state);
  return (
    <Card className='w-fit'>
      <CardContent>
        <p className='body'>{message}</p>
      </CardContent>
      <CardFooter className='flex gap-2'>
        <Button variant='ghost' onClick={() => sendMessage('Cancel')}>
          Cancel
        </Button>
        <Button onClick={() => sendMessage('Confirm')}>Confirm</Button>
      </CardFooter>
    </Card>
  );
}
