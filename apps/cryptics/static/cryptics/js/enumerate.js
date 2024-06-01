function enumerate(word){
	let symbols_in_enumeration = {
		"-": true,
		".": true,
		"/": true,
		"!": true,
	}
	word = word.toUpperCase().replace(/\s*\(.*\)\s*$/, "")  // Remove an existing enumeration if present
	let output = ""
	let count = 0
	for(let i = 0; i < word.length; i++){
	    // This regex should, fingers-crossed, match any unicode letter or ASCII digit
		if(/[\p{L}\d]/u.test(word.charAt(i))){
			count++
		} else if(symbols_in_enumeration[word[i]]) {
			if(count > 0){
				output += count
			}
			output += word[i]
			count = 0
		} else if(word[i] == " ") {
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

	return word + " (" + output + ")"
}

document.getElementById("enumerate_link").addEventListener("click", function(e){
	e.preventDefault()
	let new_contest_word = document.getElementById("new_contest_word")
	new_contest_word.value = enumerate(new_contest_word.value)
})
