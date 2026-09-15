export default function PageHeader({ title, actions, children }) {
  return (
    <header className="page-header">
      <div className="page-header-main">
        <div className="brand">
          <svg width="22" height="22" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="M20 4L4 14v12l16 10 16-10V14L20 4z" stroke="currentColor" strokeWidth="2" fill="none"/>
            <path d="M20 4v32M4 14l16 10 16-10M4 26l16-10 16 10" stroke="currentColor" strokeWidth="1.5" fill="none"/>
            <circle cx="20" cy="18" r="4" fill="currentColor"/>
          </svg>
          <p className="eyebrow">TRACK_75</p>
        </div>
        <h1>{title}</h1>
        {children}
      </div>
      {actions ? <div className="page-header-side">{actions}</div> : null}
    </header>
  );
}
