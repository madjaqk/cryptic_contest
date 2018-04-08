function enumerate(clue){
	let symbols_in_enumeration = {
		"-": true,
		".": true,
		"/": true,
		"!": true,
	}
	clue = clue.toUpperCase().replace(/\s*\(.*\)\s*$/, "")
	let output = ""
	let count = 0
	for(let i = 0; i < clue.length; i++){
		if(clue.charCodeAt(i) >= 65 && clue.charCodeAt(i) <= 90){
			count++
		} else if(symbols_in_enumeration[clue[i]]) {
			if(count > 0){
				output += count
			}
			output += clue[i]
			count = 0
		} else if(clue[i] == " ") {
			if(count > 0){
				output += count + ","
			}
			if(output.slice(-1) != " "){
				output += " "
			}
			count = 0
		}
	}

	if(count > 0){
		output += count
	}

	output = output.replace(/\D*$/, "")

	return clue + " (" + output + ")"
}

document.getElementById("enumerate_link").addEventListener("click", function(e){
	e.preventDefault()
	let new_contest_word = document.getElementById("new_contest_word")
	new_contest_word.value = enumerate(new_contest_word.value)
})