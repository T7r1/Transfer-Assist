const btn = document.getElementById("btn");
const input = document.getElementById("input");
const ls = document.getElementById("myList");

btn.addEventListener("click", () => {
  const value = input.value.trim();
  if (value) {
    const li = document.createElement("li");
    li.textContent = value;
    ls.appendChild(li);
    input.value = "";
  } else {
    alert("Please enter a list item.");
  }
});
// const addBtn = document.getElementById("addBtn");
// const newItem = document.getElementById("newItem");
// const list = document.getElementById("myList");

// addBtn.addEventListener("click", () => {
//   const value = newItem.value.trim();
//   if (value) {
//     const li = document.createElement("li");
//     li.textContent = value;
//     list.appendChild(li);
//     newItem.value = "";
//   } else {
//     alert("Please enter a list item.");
//   }
// });
