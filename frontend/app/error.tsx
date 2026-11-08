"use client"; // Error boundaries must be Client Components

import { ErrorView } from "@/components/ui/error-view";

export default function Error({ error, retry }: { error: unknown; retry: () => void }) {
  return <ErrorView error={error} retry={retry} />;
}
