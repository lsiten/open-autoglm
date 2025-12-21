// Escape HTML to prevent XSS
export const escapeHtml = (text: string): string => {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// Format think/reasoning content (amber theme)
export const formatThink = (thought: string): string => {
  if (!thought) return ''
  
  let formatted = thought
  
  // Extract and style <think> tags
  formatted = formatted.replace(
    /<think>(.*?)<\/redacted_reasoning>/gs,
    (match, content) => {
      const escaped = escapeHtml(content.trim())
      return `<div class="mb-3 p-3 bg-amber-500/15 border-l-3 border-amber-400 rounded-r text-amber-100 leading-relaxed">${escaped}</div>`
    }
  )
  
  // Remove <answer> tags from think content (they should be in answer section)
  formatted = formatted.replace(/<answer>.*?<\/answer>/gs, '')
  
  // Style step numbers
  formatted = formatted.replace(
    /(Step\s+\d+[\.:]?\s*)(.*?)(?=\n|$|Step\s+\d+)/g,
    (match, prefix, content) => {
      const escapedContent = escapeHtml(content.trim())
      return `<div class="mb-2 flex items-start gap-2"><span class="inline-flex items-center px-2 py-1 bg-amber-500/20 text-amber-300 font-semibold text-[11px] rounded shrink-0">${prefix}</span><span class="text-amber-100 flex-1">${escapedContent}</span></div>`
    }
  )
  
  // Convert line breaks
  formatted = formatted.replace(/\n\n+/g, '<br><br>')
  formatted = formatted.replace(/\n/g, '<br>')
  
  // If no special formatting, return as plain text
  if (formatted === thought) {
    return escapeHtml(thought).replace(/\n\n+/g, '<br><br>').replace(/\n/g, '<br>')
  }
  
  return formatted
}

// Format answer/action content (green theme)
export const formatAnswer = (answer: string): string => {
  if (!answer) return ''
  
  let formatted = answer
  
  // Extract and style <answer> tags
  formatted = formatted.replace(
    /<answer>(.*?)<\/answer>/gs,
    (match, content) => {
      const escaped = escapeHtml(content.trim())
      return `<div class="p-2.5 bg-green-500/15 border-l-3 border-green-400 rounded-r font-mono text-green-200 text-[12px] leading-relaxed">${escaped}</div>`
    }
  )
  
  // Highlight do(action=...) and finish(message=...) patterns
  formatted = formatted.replace(
    /(do\(action=|finish\(message=)([^)]+\))/g,
    (match) => {
      const escaped = escapeHtml(match)
      return `<span class="inline-block px-2 py-1 bg-green-500/25 text-green-200 font-mono rounded text-[12px] font-semibold">${escaped}</span>`
    }
  )
  
  // Convert line breaks
  formatted = formatted.replace(/\n\n+/g, '<br><br>')
  formatted = formatted.replace(/\n/g, '<br>')
  
  // If no special formatting, return as plain text
  if (formatted === answer) {
    return escapeHtml(answer).replace(/\n\n+/g, '<br><br>').replace(/\n/g, '<br>')
  }
  
  return formatted
}

