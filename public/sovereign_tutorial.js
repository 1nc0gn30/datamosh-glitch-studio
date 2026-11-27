/**
 * Sovereign Quickstart Tutorial Modal (Zero innerHTML sinks, Dual-Theme aware)
 * Engineered by Neal Frazier Tech (@1nc0gn30) • NullAI Platform
 */
(function () {
  if (window.__SOVEREIGN_TUTORIAL_ATTACHED__) return;
  window.__SOVEREIGN_TUTORIAL_ATTACHED__ = true;

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach((k) => {
        if (k === 'style' && typeof attrs[k] === 'object') {
          Object.assign(node.style, attrs[k]);
        } else if (k === 'text') {
          node.textContent = String(attrs[k]);
        } else {
          node.setAttribute(k, String(attrs[k]));
        }
      });
    }
    if (Array.isArray(children)) {
      children.forEach((c) => {
        if (c) node.appendChild(c);
      });
    }
    return node;
  }

  window.createSovereignTutorial = function (config) {
    const {
      toolId,
      toolName,
      tagline,
      steps = [],
      accentColor = '#D4AF37',
    } = config || {};

    if (document.getElementById(`sovTutorial-${toolId}`)) return;

    const modal = el('div', {
      id: `sovTutorial-${toolId}`,
      role: 'dialog',
      'aria-modal': 'true',
      'aria-label': `${toolName} Quickstart`,
      style: {
        display: 'none',
        position: 'fixed',
        inset: '0',
        zIndex: '999999',
        background: 'rgba(6, 8, 14, 0.82)',
        backdropFilter: 'blur(10px)',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
        boxSizing: 'border-box',
      },
    });

    const card = el('div', {
      style: {
        background: 'var(--bg-card, #11131B)',
        border: `2px solid ${accentColor}`,
        borderRadius: '16px',
        maxWidth: '600px',
        width: '100%',
        maxHeight: '90vh',
        overflowY: 'auto',
        padding: '24px',
        color: 'var(--text, #F4F4F8)',
        position: 'relative',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        boxSizing: 'border-box',
      },
    });

    const closeBtn = el('button', {
      id: `sovCloseBtn-${toolId}`,
      type: 'button',
      'aria-label': 'Close quickstart tutorial',
      text: '✕',
      style: {
        position: 'absolute',
        top: '14px',
        right: '14px',
        background: 'transparent',
        border: '1px solid var(--border, rgba(212,175,55,0.4))',
        color: 'var(--text, #F4F4F8)',
        width: '44px',
        height: '44px',
        borderRadius: '50%',
        fontSize: '16px',
        cursor: 'pointer',
        fontWeight: '700',
      },
    });

    const titleWrap = el('div', { style: { marginBottom: '14px', paddingRight: '48px' } }, [
      el('h2', {
        text: toolName || 'Quickstart',
        style: {
          margin: '0',
          fontSize: '18px',
          fontWeight: '800',
          color: 'var(--accent, #D4AF37)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        },
      }),
      el('p', {
        text: `${tagline || ''} · Local 2D Canvas & Loopback API`,
        style: { margin: '4px 0 0', color: 'var(--text-muted, #94A3B8)', fontSize: '12px' },
      }),
    ]);

    const braillePre = el('pre', {
      id: `sovBrailleCanvas-${toolId}`,
      'aria-hidden': 'true',
      style: {
        fontSize: '10px',
        lineHeight: '10px',
        color: 'var(--accent-alt, #0E7490)',
        margin: '0',
        fontFamily: 'ui-monospace, monospace',
        whiteSpace: 'pre',
      },
    });
    const brailleBox = el(
      'div',
      {
        style: {
          background: 'var(--bg-surface, #0B0D14)',
          border: '1px solid var(--border, rgba(212,175,55,0.3))',
          borderRadius: '10px',
          padding: '10px',
          marginBottom: '16px',
          textAlign: 'center',
          overflow: 'hidden',
        },
      },
      [braillePre]
    );

    const stepsList = el('div', {
      style: { display: 'flex', flexDirection: 'column', gap: '10px' },
    });
    steps.forEach((s, idx) => {
      const row = el(
        'div',
        {
          style: {
            display: 'flex',
            gap: '12px',
            background: 'var(--bg-surface, rgba(255,255,255,0.03))',
            border: '1px solid var(--border-subtle, rgba(255,255,255,0.1))',
            borderRadius: '10px',
            padding: '12px',
            alignItems: 'flex-start',
          },
        },
        [
          el('span', { text: s.icon || '▸', style: { fontSize: '20px', lineHeight: '1.2' } }),
          el('div', {}, [
            el('h4', {
              text: `Step ${idx + 1}: ${s.title || ''}`,
              style: {
                margin: '0 0 4px',
                color: 'var(--accent, #D4AF37)',
                fontSize: '13px',
                fontWeight: '700',
              },
            }),
            el('p', {
              text: s.desc || '',
              style: { margin: '0', color: 'var(--text-muted, #CBD5E1)', fontSize: '12px', lineHeight: '1.5' },
            }),
          ]),
        ]
      );
      stepsList.appendChild(row);
    });

    const actionBtn = el('button', {
      id: `sovActionBtn-${toolId}`,
      type: 'button',
      text: 'Close Quickstart',
      style: {
        background: 'var(--btn-primary-bg, #D4AF37)',
        color: 'var(--btn-primary-fg, #08080B)',
        border: 'none',
        minHeight: '44px',
        padding: '10px 22px',
        borderRadius: '999px',
        fontWeight: '800',
        fontSize: '12px',
        cursor: 'pointer',
      },
    });

    const footerRow = el(
      'div',
      {
        style: {
          marginTop: '18px',
          display: 'flex',
          justifyContent: 'flex-end',
          paddingTop: '12px',
          borderTop: '1px solid var(--border-subtle, rgba(255,255,255,0.1))',
        },
      },
      [actionBtn]
    );

    card.appendChild(closeBtn);
    card.appendChild(titleWrap);
    card.appendChild(brailleBox);
    card.appendChild(stepsList);
    card.appendChild(footerRow);
    modal.appendChild(card);
    document.body.appendChild(modal);

    let animInterval = null;
    let tick = 0;

    function renderBrailleWave() {
      tick += 0.16;
      const W = 32;
      const H = 6;
      let out = '';
      const dots = [
        [0, 0, 0x01], [0, 1, 0x02], [0, 2, 0x04], [0, 3, 0x40],
        [1, 0, 0x08], [1, 1, 0x10], [1, 2, 0x20], [1, 3, 0x80],
      ];
      for (let y = 0; y < H; y++) {
        for (let x = 0; x < W; x++) {
          let mask = 0;
          for (let d = 0; d < 8; d++) {
            const px = x * 2 + dots[d][0];
            const py = y * 4 + dots[d][1];
            const v = Math.sin(px * 0.22 + tick) * Math.cos(py * 0.35 + tick);
            if (v > 0.08) mask |= dots[d][2];
          }
          out += String.fromCharCode(0x2800 | mask);
        }
        out += '\n';
      }
      braillePre.textContent = out;
    }

    function openModal() {
      modal.style.display = 'flex';
      renderBrailleWave();
      if (!animInterval) animInterval = setInterval(renderBrailleWave, 70);
    }

    function closeModal() {
      modal.style.display = 'none';
      if (animInterval) {
        clearInterval(animInterval);
        animInterval = null;
      }
    }

    closeBtn.addEventListener('click', closeModal);
    actionBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    return { open: openModal, close: closeModal };
  };
})();
