---
id: 16977
severity: "Medium"
---

# Owner can transfer all ERC20 reward token out using function recoverERC20

## Description

The function recoverERC20 is very privileged. It means to recover any token that is accidently sent to the contract.

```solidity
function recoverERC20(address token) external onlyOwner returns(bool) {
	if(minAmountRewardToken[token] != 0) revert Errors.CannotRecoverToken();

	uint256 amount = IERC20(token).balanceOf(address(this));
	if(amount == 0) revert Errors.NullValue();
	IERC20(token).safeTransfer(owner(), amount);

	return true;
}
```

However, admin / owner can use this function to transfer all the reserved reward tokens, which result in fund loss of the pledge creator and the loss of reward for users that want to delegate the veToken.

Also, the recovered token is sent to owner directly instead of sending to a recipient address.

The safeguard

```solidity
if(minAmountRewardToken[token] != 0)
```

cannot stop owner transferring funds because if the owner is compromised or misbehaves, he can adjust the whitelist easily.

## Proof of Concept

The admin can set minAmountRewardToken[token] to 0 first by calling updateRewardToken:

```solidity
function updateRewardToken(address token, uint256 minRewardPerSecond) external onlyOwner {
```

By doing this the admin removes the token from the whitelist, then the token can call recoverERC20 to transfer all the token into the owner wallet.

```solidity
function recoverERC20(address token) external onlyOwner returns(bool) {
```

## Recommendation

We recommend that the project uses a multisig wallet to safeguard the owner’s wallet.

We can also keep track of the reserved amount for rewarding token and only transfer the remaining amount of token out.

```solidity
pledgeAvailableRewardAmounts[pledgeId] += totalRewardAmount;
reservedReward[token] += totalRewardAmount;
```

Then we can change the implementation to:

```solidity
function recoverERC20(address token, address recipient) external onlyOwner returns(bool) {

	uint256 amount = IERC20(token).balanceOf(address(this));
	if(amount == 0) revert Errors.NullValue();

	if(minAmountRewardToken[token] == 0) {
	 // if it is not whitelisted, we assume it is mistakenly sent, 
	   // we transfer the token to recipient
	 IERC20(token).safeTransfer(recipient, amount);
	} else {
	// revert if the owner over transfer
	if(amount >  reservedReward[token]) revert rewardReserved();
	  IERC20(token).safeTransfer(recipient, amount - reservedReward[token]);
	}

	return true;

}
```

Interesting proposed Mitigation to be noted.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract contains a privileged function called recoverERC20 that is intended to allow the owner to retrieve ERC20 tokens that were accidentally sent to the contract. The function checks a whitelist mapping (minAmountRewardToken) and aborts if the token is marked as a reward token, but the whitelist is mutable by the same owner through the updateRewardToken function. Because the owner (or an attacker who compromises the owner’s key) can set the whitelist entry for a reward token to zero, the guard becomes ineffective and the recoverERC20 function can be used to transfer the entire balance of that token out of the contract directly to the owner’s address. The function also hard‑codes the recipient as the owner, offering no option to send the recovered tokens to a neutral address such as a multisig or a timelocked vault. This flaw allows the owner to drain all reserved reward tokens that were meant to be distributed to pledge creators and delegators. The vulnerability manifests whenever the contract holds reward tokens and the owner decides to manipulate the whitelist or when the owner’s private key is compromised. It affects every participant who expects to receive rewards: users see their pending rewards disappear, balances in the UI show zero, and delegations yield no returns. The issue was discovered during an audit review of the token recovery logic, where the interaction between the mutable whitelist and the recovery function revealed an unintended withdrawal path. The problem is subtle because the function name suggests a harmless utility, and the whitelist check appears to protect reward tokens, making the risk easy to overlook. To remediate, the recovery mechanism should be constrained to non‑reward tokens only, enforce an immutable or multi‑signed whitelist, keep an accurate accounting of reserved reward balances, and require an explicit, auditable recipient address (e.g., a multisig) rather than sending funds directly to the owner. Implementing these controls restores the intended business logic that reward tokens remain allocated for distribution and prevents arbitrary owner‑driven fund extraction.
