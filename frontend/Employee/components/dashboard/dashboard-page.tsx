import { DashboardHero } from "./dashboard-hero";
import { StatCard } from "./stat-card";

export function DashboardPage() {
  return (
    <>
      <DashboardHero
        title="Do your best work in the "
        highlight="Employee Workspace"
        description="Stay on top of assigned work, attendance, documents, and daily delivery updates."
        action={<button type="button">Open today&apos;s tasks</button>}
      />
      <div className="dash-content">
        <section className="dash-stats" aria-label="Workspace summary">
          <StatCard label="Assigned Projects" value="5" change="2 milestones due this week" icon="globe" />
          <StatCard label="Open Tasks" value="14" change="6 are in review" icon="eye" />
          <StatCard label="Attendance" value="96%" change="1 leave request pending" icon="money" />
          <StatCard label="Docs Ready" value="9" change="Shared from company library" icon="bolt" />
        </section>
        <section className="dash-workspace-grid">
          <article className="dash-panel">
            <header>
              <h2>Work focus</h2>
              <p>Everything you need for delivery sits in one simple dashboard.</p>
            </header>
            <div className="dash-modules">
              <div>
                <em>● on track</em>
                <h3>Daily priorities</h3>
                <p>Prepare deliverables, update task notes, and close blockers fast</p>
                <strong>3 top items</strong>
              </div>
              <div>
                <em>● synced</em>
                <h3>Team updates</h3>
                <p>Managers have shared the latest sprint notes and feedback</p>
                <strong>2 new notes</strong>
              </div>
            </div>
          </article>
          <article className="dash-panel">
            <header>
              <h2>Quick actions</h2>
              <p>Move into work without extra clicks.</p>
            </header>
            <div className="dash-actions">
              <button>Start attendance check-in</button>
              <button>Open project notes</button>
            </div>
          </article>
        </section>
      </div>
    </>
  );
}
