import { DashboardHero } from "./dashboard-hero";

export function AboutPage() {
  return (
    <>
      <DashboardHero
        title="About "
        highlight="LoopLess"
        description="A connected command center built to keep every part of your digital business in one focused workspace."
        compact
      />
      <div className="dash-content">
        <article className="dash-panel dash-about-panel">
          <small>THE PLATFORM</small>
          <h2>Everything connected. Nothing complicated.</h2>
          <p>
            LoopLess brings publishing, audience, payments, and distribution together in a clean role-based platform.
          </p>
          <div className="dash-about-features">
            <div>
              <strong>Reusable</strong>
              <span>Clean component-based structure</span>
            </div>
            <div>
              <strong>Responsive</strong>
              <span>Designed for every screen size</span>
            </div>
            <div>
              <strong>Consistent</strong>
              <span>One visual language everywhere</span>
            </div>
          </div>
        </article>
      </div>
    </>
  );
}
