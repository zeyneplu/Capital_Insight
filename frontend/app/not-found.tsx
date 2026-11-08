import { ButtonLink, EmptyState } from "@/components/ui/primitives";

export default function NotFound() {
  return (
    <div className="py-8">
      <EmptyState
        title="We couldn't find that page"
        description="The record may not exist, or it belongs to an institution that isn't connected in this session."
        action={<ButtonLink href="/">Go to overview</ButtonLink>}
      />
    </div>
  );
}
