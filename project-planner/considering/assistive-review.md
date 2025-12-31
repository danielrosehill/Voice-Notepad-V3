# Feature: Assistive Review

**Status:** Considering
**Priority:** High
**Complexity:** Medium

## Summary

Conduct a comprehensive accessibility audit of Voice Notepad to ensure the app serves the assistive technology user population effectively. STT (Speech-to-Text) and TTS (Text-to-Speech) technologies have significant utility for users with disabilities, and this review aims to identify and close any accessibility gaps.

## Problem

Voice Notepad already incorporates TTS announcements for audio feedback, but a systematic accessibility review has not been conducted. The app may have gaps that prevent users relying on assistive technologies from using it effectively.

Key user groups who may benefit:
- **Vision impairments**: Users who rely on screen readers or TTS
- **Motor impairments**: Users who benefit from voice input over typing
- **Cognitive impairments**: Users who find dictation easier than typing
- **Repetitive strain injuries**: Users who need to minimize keyboard use

## Goals

1. Ensure full screen reader compatibility (NVDA, Orca, VoiceOver)
2. Verify keyboard-only navigation works throughout the app
3. Confirm TTS announcements cover all critical actions
4. Review color contrast and visual accessibility
5. Document accessibility features for users

## Audit Areas

### 1. Screen Reader Compatibility

- [ ] All UI elements have proper accessible names
- [ ] Focus order is logical
- [ ] State changes are announced (recording, transcribing, etc.)
- [ ] Error messages are accessible
- [ ] Tables and lists are properly structured

### 2. Keyboard Navigation

- [ ] All functions accessible via keyboard
- [ ] Focus indicators are visible
- [ ] No keyboard traps
- [ ] Shortcuts don't conflict with assistive technology
- [ ] Tab order follows visual layout

### 3. Audio Feedback (TTS)

Current TTS announcements:
- Recording started/stopped
- Transcription started/complete
- Audio cached/cleared
- Text copied to clipboard
- Format/tone/style changes
- Mode changes (verbatim, general)
- Errors

**Review needed:**
- [ ] Are all critical state changes announced?
- [ ] Is timing appropriate (not too fast, not overlapping)?
- [ ] Can users distinguish between different announcements?
- [ ] Are announcements clear and concise?

### 4. Visual Accessibility

- [ ] Color contrast meets WCAG AA (4.5:1 for text)
- [ ] Information not conveyed by color alone
- [ ] Text is resizable without loss of functionality
- [ ] UI remains usable at 200% zoom

### 5. Motor Accessibility

- [ ] Click targets are adequately sized (44x44px minimum)
- [ ] No time-sensitive interactions without alternatives
- [ ] Drag-and-drop has keyboard alternatives
- [ ] Global hotkeys work for hands-free operation

## PyQt6 Accessibility Considerations

- Use `setAccessibleName()` and `setAccessibleDescription()` on widgets
- Ensure proper `QAccessible` roles are set
- Test with `QT_ACCESSIBILITY=1` environment variable
- Consider `QAccessibleWidget` subclasses for custom widgets

## Files to Review

| File | Focus Area |
|------|------------|
| `main.py` | Main window accessibility, focus management |
| `history_widget.py` | Table/list accessibility |
| `cost_widget.py` | Data table accessibility |
| `analysis_widget.py` | Chart accessibility (alt text?) |
| `about_widget.py` | Keyboard shortcuts documentation |
| `tts_announcer.py` | TTS coverage completeness |

## Implementation Steps

1. [ ] Install screen reader (Orca) for testing
2. [ ] Document current accessibility state
3. [ ] Identify gaps using WCAG 2.1 checklist
4. [ ] Prioritize fixes by impact
5. [ ] Add missing accessible names/descriptions
6. [ ] Expand TTS announcements if needed
7. [ ] Test keyboard-only navigation flow
8. [ ] Fix visual contrast issues
9. [ ] Create accessibility documentation for users
10. [ ] Consider user testing with assistive tech users

## Success Criteria

- App passes WCAG 2.1 Level AA for applicable criteria
- Full functionality available via keyboard only
- Screen reader users can complete core workflows
- TTS mode provides complete audio feedback
- Accessibility features documented in user guide

## Resources

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [PyQt Accessibility](https://doc.qt.io/qt-6/accessible.html)
- [Orca Screen Reader](https://help.gnome.org/users/orca/stable/)

## Notes

This review is motivated by recognizing the significant value STT/TTS technologies provide to the assistive user population. Ensuring Voice Notepad is fully accessible is both a responsibility and an honor.
