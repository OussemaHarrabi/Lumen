import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";

export default async function WorkspacePage({
  searchParams,
}: {
  searchParams: Promise<{ empty?: string }>;
}) {
  const params = await searchParams;
  return <WorkspaceShell initialEmpty={params.empty === "1"} />;
}
