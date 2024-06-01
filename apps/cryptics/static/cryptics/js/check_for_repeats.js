
document.getElementById("repeats_link").addEventListener("click", async function(e){
	e.preventDefault()

	const new_contest_word_element = document.getElementById("new_contest_word")
	const repeats_target_element = document.getElementById("repeats_target")

	let word = new_contest_word.value
	word = word.toUpperCase().replace(/\s*\(.*\)\s*$/, "")  // Remove an enumeration if present

	if (!word) { return false }

    repeats_target_element.classList.remove("warning")
	repeats_target_element.innerText = "..."

	const url = "/contest/search?" + new URLSearchParams({"search": word}).toString()

	let res = await fetch(url)
	let json = await res.json()
	console.log(json)

	if (!res.ok){
	    repeats_target_element.classList.add("warning")
	    if (json["errors"] && json["errors"]["search"]) {
	        repeats_target_element.innerText = json['errors']['search'].join(', ')
	    } else {
	        repeats_target_element.innerText = "Error: Check for repeats failed"
	    }
	} else {
        if (json.contests && json.contests.length ) {
            let links = json.contests.map(contest => `<a href="${contest.url}">${contest.word.replace(/</g, "&lt;")}</a>`)
            repeats_target_element.innerHTML = "⚠️ Possible repeats: " + links.join(", ")
        } else {
            repeats_target_element.innerText = "✅ No repeats found!"
        }
	}

})
