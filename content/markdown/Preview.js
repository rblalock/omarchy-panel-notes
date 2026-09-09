// Split only top-level presentation blocks; Qt still renders Markdown inside
// text and quotes. The source document is never rewritten by this formatter.
function blocks(source) {
    var lines = source.replace(/\r\n?/g, "\n").split("\n")
    var result = [], pending = [], list = false
    function flush() {
        if (pending.join("\n").trim()) result.push({kind:"text", text:pending.join("\n")})
        pending = []; list = false
    }
    function boundary(line) {
        return /^ {0,3}(?:!\[|#{1,6}\s|>|`{3,}|~{3,}|(?:[-+*]|\d+[.)])\s)/.test(line)
    }
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i]
        // Keep nested/list content together for Qt's Markdown parser.
        if (/^ {0,3}(?:[-+*]|\d+[.)])\s/.test(line)) list = true
        if (list && line && !/^\s/.test(line) && !/^([-+*]|\d+[.)])\s/.test(line) &&
            (boundary(line) || (i > 0 && !lines[i-1].trim()))) flush()
        if (list) { pending.push(line); continue }
        var fence = line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/)
        if (fence && !(fence[1][0] === "`" && fence[2].indexOf("`") >= 0)) {
            flush()
            var code = [], close = new RegExp("^ {0,3}" + fence[1][0] + "{" + fence[1].length + ",}\\s*$")
            while (++i < lines.length && !close.test(lines[i])) code.push(lines[i])
            result.push({kind:"code", text:code.join("\n")})
            continue
        }
        if (/^ {0,3}>/.test(line)) {
            flush()
            var quote = []
            while (i < lines.length) {
                var marked = lines[i].match(/^ {0,3}> ?(.*)$/)
                if (marked) quote.push(marked[1])
                // CommonMark permits lazy paragraph continuation inside a quote.
                else if (lines[i].trim() && !boundary(lines[i]) && quote.length && quote[quote.length-1].trim()) quote.push(lines[i])
                else break
                i++
            }
            i--
            result.push({kind:"quote", text:quote.join("\n")})
            continue
        }
        var image = line.match(/^!\[([^\]]*)\]\((assets\/[a-f0-9]+\.(?:png|jpg|webp))\)\s*$/)
        if (image) { flush(); result.push({kind:"image", path:image[2], alt:image[1]}); continue }
        if (/^ {0,3}#{1,6}(\s|$)/.test(line)) { flush(); result.push({kind:"text", text:line}); continue }
        pending.push(line)
    }
    flush()
    return result
}

function markdown(source) {
    var fence = "", length = 0
    return source.split("\n").map(function(line) {
        var marker = line.match(/^\s*(`{3,}|~{3,})/)
        if (marker) {
            if (!fence) { fence = marker[1][0]; length = marker[1].length }
            else if (marker[1][0] === fence && marker[1].length >= length && /^\s*[`~]+\s*$/.test(line)) fence = ""
            return line
        }
        if (fence || /^( {4}|\t)/.test(line)) return line
        // Keep source-authored HTML inert and external images unloaded.
        line = line.replace(/<[^>]*>/g, function(tag) { return tag.replace(/</g,"&lt;").replace(/>/g,"&gt;") })
            .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, function(match, alt, path) {
                return /^assets\/[a-f0-9]+\.(png|jpg|webp)$/.test(path) ? match : "[Image: " + alt + "]"
            })
        if (/^\s*\[[^\]]+\]:\s*\S+/.test(line)) return ""
        // Show ordinary entered line breaks, while leaving structural Markdown
        // (tables, headings, lists and thematic rules) to the native parser.
        if (line.trim() && !/[|]/.test(line) && !/^ {0,3}(?:#{1,6}(?:\s|$)|(?:[-+*]|\d+[.)])\s|[-=_*]{3,}\s*$)/.test(line) && !/\\$| {2}$/.test(line)) line += "  "
        return line
    }).join("\n")
}
