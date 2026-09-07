let quantity = 10;
document.querySelector("#increment").addEventListener("click", () => {
  quantity -= 1;
  document.querySelector("#quantity").textContent = String(quantity);
});
