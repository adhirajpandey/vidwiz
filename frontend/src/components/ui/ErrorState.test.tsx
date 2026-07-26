import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import ErrorState from './ErrorState';

describe('ErrorState', () => {
  it('renders a persistent message, retry action, and support reference', () => {
    const html = renderToStaticMarkup(
      <ErrorState
        title="Unable to load videos"
        message="Check your connection and try again."
        referenceId="request-123"
        onRetry={() => undefined}
      />
    );

    expect(html).toContain('Unable to load videos');
    expect(html).toContain('Check your connection and try again.');
    expect(html).toContain('Reference: request-123');
    expect(html).toContain('Try again');
    expect(html).toContain('role="alert"');
  });
});
