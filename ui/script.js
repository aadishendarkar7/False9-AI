/* ============================================================
   Defensive version: every section is isolated so a problem in
   one (e.g. a missing element) can NEVER stop the rest of the
   script from running — this is what was breaking your buttons.
   ============================================================ */

/* ---------- auto-resize the iframe to match real content height ----------
   components.html locks in a fixed pixel height from Python, which is why
   there was dead space below the cards/footer. window.frameElement gives
   same-origin access to the actual <iframe> element in the Streamlit page,
   so we can just measure our own content and set the iframe to fit it.
   A ResizeObserver (rather than a handful of fixed timeouts) keeps this
   correct even when late font loads or layout shifts change the height. */
function autoResizeIframe(){
  try {
    if (window.frameElement) {
      const h = document.documentElement.scrollHeight;
      window.frameElement.style.height = h + "px";
    }
  } catch (err) {
    console.warn("[False9] auto-resize unavailable, using the fixed height from app.py:", err);
  }
}
autoResizeIframe();
window.addEventListener("load", autoResizeIframe);

if ("ResizeObserver" in window) {
  const ro = new ResizeObserver(() => autoResizeIframe());
  ro.observe(document.documentElement);
} else {
  // very old browser fallback
  setTimeout(autoResizeIframe, 400);
  setTimeout(autoResizeIframe, 1200);
}

if (document.fonts && document.fonts.ready) {
  document.fonts.ready.then(autoResizeIframe);
}
window.addEventListener("resize", autoResizeIframe);

/* ---------- boot sequence (purely decorative overlay — never hides content) ---------- */
try {
  const bootScreen = document.getElementById("bootScreen");
  const bootLines = document.getElementById("bootLines");

  const sequence = [
    "Initializing Tactical Engine...",
    "Loading Match Intelligence...",
    "Loading Neural Analysis...",
    "Loading Prediction Engine...",
  ];

  if (bootScreen && bootLines) {
    let i = 0;
    const step = () => {
      if (i < sequence.length) {
        const line = document.createElement("div");
        line.className = "boot-line";
        line.textContent = sequence[i];
        bootLines.appendChild(line);
        requestAnimationFrame(() => line.classList.add("visible"));
        i++;
        setTimeout(step, 350);
      } else {
        const status = document.createElement("div");
        status.className = "boot-line status";
        status.textContent = "SYSTEM ONLINE";
        bootLines.appendChild(status);
        requestAnimationFrame(() => status.classList.add("visible"));
        setTimeout(() => {
          bootScreen.classList.add("boot-hidden");
          setTimeout(() => bootScreen.remove(), 700);
        }, 450);
      }
    };
    setTimeout(step, 250);
  }
} catch (err) {
  console.error("[False9] boot sequence failed (hero is unaffected):", err);
  const b = document.getElementById("bootScreen");
  if (b) b.remove();
}

/* ---------- floodlight mouse glow ---------- */
try {
  const glow = document.createElement("div");
  glow.className = "mouseGlow";
  glow.style.opacity = "0"; // hidden until the cursor actually enters
  glow.style.transition = "opacity .3s ease";
  document.body.appendChild(glow);

  document.addEventListener("mousemove", (e) => {
    glow.style.opacity = "1";
    glow.style.left = e.clientX + "px";
    glow.style.top = e.clientY + "px";
  });
  // hide it instead of leaving it frozen in place once the cursor leaves
  // the iframe (this was the stray glow "smudge" you saw near the bottom)
  document.addEventListener("mouseleave", () => {
    glow.style.opacity = "0";
  });
} catch (err) { console.error("[False9] mouse glow failed:", err); }

/* ---------- typewriter ---------- */
try {
  const phrases = ["Analyze.", "Predict.", "Create."];
  const label = document.getElementById("typingLabel");
  if (label) {
    let phraseIndex = 0, charIndex = 0, deleting = false;
    (function typeLoop(){
      const current = phrases[phraseIndex];
      if (!deleting) {
        charIndex++;
        label.textContent = current.slice(0, charIndex);
        if (charIndex === current.length) {
          deleting = true;
          setTimeout(typeLoop, 1100);
          return;
        }
      } else {
        charIndex--;
        label.textContent = current.slice(0, charIndex);
        if (charIndex === 0) {
          deleting = false;
          phraseIndex = (phraseIndex + 1) % phrases.length;
        }
      }
      setTimeout(typeLoop, deleting ? 45 : 90);
    })();
  } else {
    console.warn("[False9] #typingLabel not found — is hero.html up to date?");
  }
} catch (err) { console.error("[False9] typewriter failed:", err); }

/* ---------- kickoff transition ---------- */
function triggerKickoff(onDone){
  console.log("[False9] triggerKickoff() called");
  try {
    const flash = document.createElement("div");
    flash.className = "kickoff-overlay active";
    document.body.appendChild(flash);
    console.log("[False9] flash element appended:", flash);

    const lines = document.createElement("div");
    lines.className = "kickoff-lines active";
    document.body.appendChild(lines);

    setTimeout(() => {
      flash.remove();
      lines.remove();
      console.log("[False9] flash removed, running onDone");
      if (onDone) onDone();
    }, 900);
  } catch (err) {
    console.error("[False9] kickoff animation failed:", err);
    if (onDone) onDone();
  }
}

/* ---------- goal celebration (plays when a quick-prompt card is clicked) ---------- */
function triggerGoalCelebration(onDone){
  console.log("[False9] triggerGoalCelebration() called");
  try {
    const overlay = document.createElement("div");
    overlay.className = "goal-overlay active";

    const net = document.createElement("div");
    net.className = "goal-net";
    overlay.appendChild(net);

    const ball = document.createElement("div");
    ball.className = "goal-ball";
    ball.textContent = "⚽";
    overlay.appendChild(ball);

    const text = document.createElement("div");
    text.className = "goal-text";
    text.textContent = "GOAL!";
    overlay.appendChild(text);

    // particle burst, radiating outward at evenly spaced angles
    const particleCount = 14;
    for (let i = 0; i < particleCount; i++) {
      const p = document.createElement("div");
      p.className = "goal-particle";
      const angle = ((Math.PI * 2) / particleCount) * i + Math.random() * 0.3;
      const dist = 90 + Math.random() * 70;
      p.style.setProperty("--dx", Math.cos(angle) * dist + "px");
      p.style.setProperty("--dy", Math.sin(angle) * dist + "px");
      overlay.appendChild(p);
    }

    document.body.appendChild(overlay);

    // impact shake, timed to when the ball hits the net
    setTimeout(() => {
      document.body.classList.add("shake");
      setTimeout(() => document.body.classList.remove("shake"), 400);
    }, 420);

    setTimeout(() => {
      overlay.remove();
      if (onDone) onDone();
    }, 1500);
  } catch (err) {
    console.error("[False9] goal celebration failed:", err);
    if (onDone) onDone();
  }
}

/* ---------- real page navigation, via hidden proxy widgets in app.py ----------
   Same underlying idea as the old chat-autofill hack, aimed at navigation:
   app.py renders real (visually hidden) Streamlit buttons/text_input. A
   genuine .click() on a real Streamlit button triggers a genuine rerun —
   which is how we get from "click inside a sandboxed iframe" to
   "st.switch_page() actually runs" without any unofficial API. */
function clickNavButton(label){
  try {
    const doc = window.parent.document;
    const buttons = doc.querySelectorAll('[data-testid="stButton"] button');
    const target = Array.from(buttons).find((b) => b.textContent.trim() === label);
    if (target) {
      target.click();
      return true;
    }
    console.warn(`[False9] nav button "${label}" not found — is app.py up to date?`);
  } catch (err) {
    console.warn("[False9] navigation failed:", err);
  }
  return false;
}

function ripple(el){
  try {
    const ring = document.createElement("div");
    ring.className = "pulse-ring active";
    el.appendChild(ring);
    setTimeout(() => ring.remove(), 500);
  } catch (err) { console.error("[False9] ripple failed:", err); }
}

/* ---------- wire up buttons/cards ---------- */
try {
  const cta = document.getElementById("enterArena");
  if (cta) {
    cta.addEventListener("click", (e) => {
      console.log("[False9] Enter the Arena clicked");
      ripple(e.currentTarget);
      triggerKickoff(() => clickNavButton("nav_dashboard"));
    });
  } else {
    console.warn("[False9] #enterArena button not found in the DOM.");
  }
} catch (err) { console.error("[False9] CTA wiring failed:", err); }

try {
  const cards = document.querySelectorAll(".card");
  console.log(`[False9] found ${cards.length} cards`);
  cards.forEach((card) => {
    card.style.cursor = "pointer";
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.addEventListener("click", (e) => {
      ripple(e.currentTarget);
      const nav = card.dataset.nav;
      const navButtonMap = {
        tracking: "nav_tracking",
        statistics: "nav_statistics",
        assistant: "nav_assistant",
      };
      triggerGoalCelebration(() => {
        if (navButtonMap[nav]) clickNavButton(navButtonMap[nav]);
      });
    });
    card.addEventListener("keypress", (e) => {
      if (e.key === "Enter") card.click();
    });
  });
} catch (err) { console.error("[False9] card wiring failed:", err); }