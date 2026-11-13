import { DashboardHero } from "./dashboard-hero";
import { StatCard } from "./stat-card";

export function DashboardPage() {
  return (
    <>
      <DashboardHero
        title="Lead your "
        highlight="Manager Workspace"
        description="Track delivery, client momentum, and team execution from one clean Adverse command center."
        action={<button type="button">Open team board</button>}
      />
      <div className="dash-content">
        <section className="dash-stats" aria-label="Workspace summary">
          <StatCard label="Active Clients" value="12" change="3 need follow-up today" icon="globe" />
          <StatCard label="Projects In Flight" value="8" change="2 pending approvals" icon="eye" />
          <StatCard label="Team Capacity" value="86%" change="4 teammates online" icon="money" />
          <StatCard label="This Week Health" value="Good" change="Delivery rhythm on track" icon="bolt" />
        </section>
        <section className="dash-workspace-grid">
          <article className="dash-panel">
            <header>
              <h2>Execution overview</h2>
              <p>Stay close to pipeline movement, blockers, and delivery ownership.</p>
            </header>
            <div className="dash-modules">
              <div>
                <em>● ready</em>
                <h3>Client queue</h3>
                <p>7 conversations active across retained accounts</p>
                <strong>2 escalations</strong>
              </div>
              <div>
                <em>● moving</em>
                <h3>CRM pipeline</h3>
                <p>5 qualified leads ready for next action</p>
                <strong>₹4.8L forecast</strong>
              </div>
            </div>
          </article>
          <article className="dash-panel">
            <header>
              <h2>Quick actions</h2>
              <p>Jump into the most common manager workflows.</p>
            </header>
            <div className="dash-actions">
              <button>Review project status</button>
              <button>Open CRM handoff</button>
            </div>
          </article>
        </section>
      </div>
    </>
  );
}
