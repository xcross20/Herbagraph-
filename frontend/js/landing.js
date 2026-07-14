(function () {
  "use strict";

  const nav = document.querySelector(".landing-nav");
  if (nav) {
    const onScroll = () => nav.classList.toggle("is-scrolled", window.scrollY > 48);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  const revealEls = document.querySelectorAll(".reveal");
  if (revealEls.length && "IntersectionObserver" in window) {
    const revealObs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-visible");
            revealObs.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    revealEls.forEach((el) => revealObs.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("is-visible"));
  }

  const journeyStages = document.querySelectorAll(".journey-stage");
  const journeyValue = document.querySelector(".journey-value");
  if (journeyStages.length && "IntersectionObserver" in window) {
    const stageObs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) e.target.classList.add("is-visible");
        });
      },
      { threshold: 0.4, rootMargin: "-10% 0px -30% 0px" }
    );
    journeyStages.forEach((s) => stageObs.observe(s));

    if (journeyValue) {
      const shrinkObs = new IntersectionObserver(
        (entries) => {
          entries.forEach((e) => {
            journeyValue.style.transform = e.isIntersecting ? "scale(0.55)" : "scale(1)";
            journeyValue.style.opacity = e.isIntersecting ? "0.35" : "1";
          });
        },
        { threshold: 0, rootMargin: "-20% 0px -50% 0px" }
      );
      const anchor = document.querySelector(".journey-value-block");
      if (anchor) shrinkObs.observe(anchor);
    }
  } else {
    journeyStages.forEach((s) => s.classList.add("is-visible"));
  }

  const pipelineSteps = document.querySelectorAll(".pipeline-step");
  if (pipelineSteps.length) {
    let active = 0;
    const cycle = () => {
      pipelineSteps.forEach((s, i) => s.classList.toggle("is-active", i === active));
      active = (active + 1) % pipelineSteps.length;
    };
    cycle();
    const interval = setInterval(cycle, 1800);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) clearInterval(interval);
    });
  }

  const heroMeta = document.querySelector(".hero-meta-br strong + span");
  if (heroMeta) {
    let n = 14;
    setInterval(() => {
      n = 13 + Math.floor(Math.random() * 3);
      heroMeta.textContent = String(n);
    }, 4200);
  }
})();