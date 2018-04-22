function click_to_reveal(el){
	if(el.classList){
		el.classList.remove("explanation")
	} else {
		el.className = el.className.replace(new RegExp('(^|\\b)explanation(\\b|$)', 'gi'), ' ');
	}
}

var elements = document.querySelectorAll(".explanation");
Array.prototype.forEach.call(elements, function(el, i){
	el.addEventListener("click", function(){ click_to_reveal(el) })
});

// Thank you to youmightnotneedjquery.com for the remove class and add event listener to all elements code