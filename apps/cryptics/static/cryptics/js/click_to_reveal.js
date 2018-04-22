function click_to_reveal(el){
	if(el.classList){
		el.classList.toggle("explanation")
	} else {
		var classes = el.className.split(" ")
		var existing_index = classes.indexOf("explanation")

		if(existing_index >= 0){
			classes.splice(existing_index, 1)
		} else {
			classes.push("explanation")
		}

		el.className = classes.join(" ")
	}
}

var elements = document.querySelectorAll(".explanation");
Array.prototype.forEach.call(elements, function(el, i){
	el.addEventListener("click", function(){ click_to_reveal(el) })
});

// Thank you to youmightnotneedjquery.com for the remove class and add event listener to all elements code