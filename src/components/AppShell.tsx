import BottomNav from "./BottomNav";
import TopNav from "./TopNav";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-screen bg-background-dark">
      <div
        aria-hidden
        className="machine-grid pointer-events-none fixed inset-0 z-0"
      />
      <div className="relative z-10">
        <div className="hidden md:block">
          <TopNav />
        </div>

        <main id="main" tabIndex={-1} className="px-5 pb-28 pt-8 md:px-12 md:pb-16 md:pt-10">
          <div className="mx-auto w-full max-w-[1440px]">{children}</div>
        </main>

        <div className="md:hidden">
          <BottomNav />
        </div>
      </div>
    </div>
  );
}
