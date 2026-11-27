import { useId, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import Icon from './Icon';

type WindowMode = 'normal' | 'minimised' | 'maximised';

export default function EarthWindow({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<WindowMode>('normal');
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const maximise = useRef<HTMLButtonElement>(null);
  const id = useId();

  useLayoutEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (mode === 'maximised') {
      element.showModal();
      maximise.current?.focus({ preventScroll: true });
      const overflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = overflow; element.close(); };
    }
    element.show();
    trigger.current?.focus({ preventScroll: true });
    trigger.current = null;
    return () => element.close();
  }, [mode]);

  return <dialog ref={dialog} id={id} className={`panel globewrap earth-window earth-window-${mode}`}
    role={mode === 'maximised' ? 'dialog' : 'region'} aria-label="Earth viewer" aria-modal={mode === 'maximised' ? true : undefined}
    onCancel={(event) => { event.preventDefault(); setMode('normal'); }}
    onKeyDown={(event) => { if (mode === 'maximised' && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') setMode('normal'); }}>
    <div className="earth-window-summary"><Icon name="globe" size={22} /><div><h3>Earth viewer</h3><p>Minimised · Restore to continue exploring</p></div></div>
    <div className="earth-window-toolbar" role="group" aria-label="Earth window size">
      <button type="button" aria-controls={id} aria-expanded={mode !== 'minimised'}
        aria-label={mode === 'minimised' ? 'Restore Earth viewer' : 'Minimise Earth viewer'}
        title={mode === 'minimised' ? 'Restore Earth viewer' : 'Minimise Earth viewer'}
        onClick={(event) => { trigger.current = event.currentTarget; setMode(mode === 'minimised' ? 'normal' : 'minimised'); }}>
        <Icon name={mode === 'minimised' ? 'restore' : 'minimise'} size={18} />
      </button>
      <button ref={maximise} type="button" aria-controls={id} aria-pressed={mode === 'maximised'}
        aria-label={mode === 'maximised' ? 'Restore Earth viewer' : 'Maximise Earth viewer'}
        title={mode === 'maximised' ? 'Restore Earth viewer · Esc' : 'Maximise Earth viewer'}
        onClick={(event) => { trigger.current = event.currentTarget; setMode(mode === 'maximised' ? 'normal' : 'maximised'); }}>
        <Icon name={mode === 'maximised' ? 'restore' : 'maximise'} size={17} />
      </button>
    </div>
    {children}
  </dialog>;
}
